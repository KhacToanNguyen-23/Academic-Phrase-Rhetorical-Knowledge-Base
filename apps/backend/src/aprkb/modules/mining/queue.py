"""PostgreSQL job claiming with bounded stale-lock recovery."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.mining.models import Job


async def claim_next(
    session: AsyncSession, *, now: datetime | None = None, stale_after_seconds: int = 300
) -> Job | None:
    claimed_at = now or datetime.now(UTC)
    stale_before = claimed_at - timedelta(seconds=stale_after_seconds)
    statement = (
        select(Job)
        .where(
            or_(
                Job.status == "queued",
                (Job.status == "processing") & (Job.locked_at < stale_before),
            )
        )
        .order_by(Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = await session.scalar(statement)
    if job is None:
        return None
    job.status = "processing"
    job.locked_at = claimed_at
    job.attempts += 1
    job.error = None
    await session.flush()
    return job
