"""PostgreSQL leasing, bounded recovery, and transaction-scoped execution locks."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.mining.models import Job, JobAttempt
from aprkb.modules.mining.operations import finish_attempt


async def execution_lock(session: AsyncSession, identity: str, *, wait: bool = False) -> bool:
    # Stable signed bigint, unlike Python's process-randomized hash().
    key = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8], signed=True)
    if wait:
        await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        return True
    return bool(await session.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}))


async def claim_next(
    session: AsyncSession, *, now: datetime | None = None, stale_after_seconds: float = 300
) -> Job | None:
    claimed_at = now or datetime.now(UTC)
    stale_before = claimed_at - timedelta(seconds=stale_after_seconds)
    statement = (
        select(Job)
        .where(
            or_(
                (Job.status == "queued")
                & or_(Job.next_attempt_at.is_(None), Job.next_attempt_at <= claimed_at),
                (Job.status == "processing")
                & or_(Job.locked_at.is_(None), Job.locked_at < stale_before),
            )
        )
        .order_by(Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    while (job := await session.scalar(statement)) is not None:
        # Keyset traversal locks one candidate at a time, not the whole queue.
        statement = statement.where(tuple_(Job.created_at, Job.id) > (job.created_at, job.id))
        # Even a stalled heartbeat must not evict a live handler transaction.
        if not await execution_lock(session, f"job:{job.id}"):
            continue
        if job.status == "processing":
            job.error_code = "lease_expired"
            job.error = "Worker lease expired before completion"
            job.next_attempt_at = None
            await finish_attempt(session, job, outcome="interrupted", now=claimed_at)
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.error_code = "attempts_exhausted"
            job.error = "Maximum processing attempts reached"
            job.locked_at = None
            job.lock_token = None
            job.next_attempt_at = None
            continue
        job.status = "processing"
        job.locked_at = claimed_at
        job.lock_token = uuid4()
        job.attempts += 1
        job.next_attempt_at = None
        job.progress_stage = "starting"
        job.progress_completed = None
        job.progress_total = None
        session.add(
            JobAttempt(
                job_id=job.id,
                attempt_no=job.attempts,
                started_at=claimed_at,
                outcome="processing",
                stage="starting",
            )
        )
        await session.flush()
        return job
    await session.flush()
    return None
