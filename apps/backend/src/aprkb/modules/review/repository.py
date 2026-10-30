"""Database access for pending candidate reviews and locked decisions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.mining.models import Candidate
from aprkb.modules.patterns.models import ReviewDecision


async def pending_candidates(session: AsyncSession) -> list[Candidate]:
    return list(
        await session.scalars(
            select(Candidate)
            .where(Candidate.status == "pending")
            .order_by(Candidate.created_at, Candidate.id)
        )
    )


async def lock_candidate(session: AsyncSession, candidate_id: UUID) -> Candidate | None:
    return await session.scalar(
        select(Candidate).where(Candidate.id == candidate_id).with_for_update()
    )


async def decisions_for_candidate(
    session: AsyncSession, candidate_id: UUID
) -> list[ReviewDecision]:
    return list(
        await session.scalars(
            select(ReviewDecision)
            .where(ReviewDecision.candidate_id == candidate_id)
            .order_by(ReviewDecision.round)
        )
    )
