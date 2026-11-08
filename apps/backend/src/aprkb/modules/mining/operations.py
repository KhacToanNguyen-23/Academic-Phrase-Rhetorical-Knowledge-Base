"""Job lifecycle history and operator actions. No source text or secrets are stored here."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.config import settings
from aprkb.modules.audit.service import record_event
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.models import Job, JobAlert, JobAttempt

RETRYABLE_JOB_TYPES = frozenset({"import_articles", "ingest_article", "mine_article"})


async def finish_attempt(
    session: AsyncSession, job: Job, *, outcome: str, now: datetime | None = None
) -> None:
    """Called while the caller owns the job row/transaction; safe to repeat."""
    ended = now or datetime.now(UTC)
    attempt = await session.scalar(
        select(JobAttempt).where(
            JobAttempt.job_id == job.id,
            JobAttempt.attempt_no == job.attempts,
        )
    )
    if attempt is None or attempt.ended_at is not None:
        return
    attempt.ended_at = ended
    attempt.outcome = outcome
    attempt.error_code = job.error_code
    attempt.error = job.error
    attempt.next_attempt_at = job.next_attempt_at
    # Progress is already recorded independently, including when output rolled back.
    await session.flush()
    alert = await session.scalar(select(JobAlert).where(JobAlert.job_id == job.id))
    if outcome == "succeeded":
        if alert is not None:
            alert.active = False
            alert.resolved_at = ended
        return
    count = int(
        await session.scalar(
            select(func.count())
            .select_from(JobAttempt)
            .where(
                JobAttempt.job_id == job.id,
                JobAttempt.outcome.in_(["failed", "interrupted"]),
            )
        )
        or 0
    )
    if count < settings.job_failure_alert_threshold:
        return
    if alert is None:
        alert = JobAlert(job_id=job.id, failure_count=count, last_failed_at=ended)
        session.add(alert)
    alert.failure_count = count
    alert.last_error_code = job.error_code
    alert.last_failed_at = ended
    alert.active = True
    alert.resolved_at = None
    alert.acknowledged_at = None
    alert.acknowledged_by = None


async def retry_manually(
    session: AsyncSession,
    *,
    job_id: UUID,
    expected_attempts: int,
    rationale: str,
    actor: ApiClient,
    request_id: str,
) -> Job:
    job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "failed" or job.attempts != expected_attempts:
        raise HTTPException(status_code=409, detail="Job changed; refresh before retrying")
    if job.type not in RETRYABLE_JOB_TYPES:
        raise HTTPException(status_code=409, detail="This job type does not support manual retry")
    if job.manual_retries >= settings.job_manual_retry_limit:
        raise HTTPException(status_code=409, detail="Manual retry limit reached")
    # Do not reset attempts/history or silently grant another automatic retry cycle.
    job.max_attempts = job.attempts + 1
    job.manual_retries += 1
    job.status = "queued"
    job.lock_token = None
    job.locked_at = None
    job.next_attempt_at = None
    job.progress_stage = "waiting_for_retry"
    job.progress_completed = None
    job.progress_total = None
    await record_event(
        session,
        actor_id=actor.id,
        action="job.retry.manual",
        entity_type="job",
        entity_id=job.id,
        after={
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "manual_retries": job.manual_retries,
            "rationale_sha256": hashlib.sha256(rationale.encode()).hexdigest(),
        },
        request_id=request_id,
    )
    await session.commit()
    await session.refresh(job)
    return job


async def acknowledge_alert(
    session: AsyncSession,
    *,
    alert_id: UUID,
    expected_last_failed_at: datetime,
    actor: ApiClient,
    request_id: str,
) -> JobAlert:
    alert = await session.scalar(select(JobAlert).where(JobAlert.id == alert_id).with_for_update())
    if alert is None:
        raise HTTPException(status_code=404, detail="Job alert not found")
    if not alert.active or alert.last_failed_at != expected_last_failed_at:
        raise HTTPException(status_code=409, detail="Alert changed; refresh before acknowledging")
    if alert.acknowledged_at is None:
        alert.acknowledged_at = datetime.now(UTC)
        alert.acknowledged_by = actor.id
        await record_event(
            session,
            actor_id=actor.id,
            action="job.alert.acknowledge",
            entity_type="job_alert",
            entity_id=alert.id,
            after={"failure_count": alert.failure_count},
            request_id=request_id,
        )
    await session.commit()
    return alert
