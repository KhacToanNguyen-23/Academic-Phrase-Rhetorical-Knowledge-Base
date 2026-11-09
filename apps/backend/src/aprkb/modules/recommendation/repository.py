"""Database loading for preloaded recommendation views and result logs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.patterns.read_model import PatternRead, load_current_patterns
from aprkb.modules.recommendation.models import RecommendationLog
from aprkb.shared.models import RefEnum


async def load_pattern_rows(
    session: AsyncSession,
    *,
    intent_code: str | None,
    query: str | None = None,
    move_code: str | None = None,
    claim_type: str | None = None,
    genre_code: str | None = None,
    journal_id: UUID | None = None,
    internal_use_codes: frozenset[str] = frozenset(),
) -> list[PatternRead]:
    """FR-07.1: retrieve candidates using normalized keyword substrings."""
    # FR-07.2 gating happens in the pipeline after retrieval and before ranking
    # or returning any candidate.
    return await load_current_patterns(
        session,
        intent_code=intent_code,
        status="approved",
        genre_code=genre_code,
        journal_id=journal_id,
        query=query,
        normalize_query=True,
        move_code=move_code,
        claim_type=claim_type,
        internal_use_codes=internal_use_codes,
    )


async def reference_strengths(session: AsyncSession) -> list[RefEnum]:
    return list(
        await session.scalars(
            select(RefEnum)
            .where(RefEnum.group.in_(["epistemic_strength", "evidence_level"]))
            .order_by(RefEnum.group, RefEnum.order)
        )
    )


async def add_recommendation_log(
    session: AsyncSession,
    *,
    request: dict[str, object],
    results: dict[str, object],
    policy_versions: dict[str, str],
    created_by: UUID,
) -> RecommendationLog:
    log = RecommendationLog(
        request=request,
        results=results,
        policy_versions=policy_versions,
        created_by=created_by,
    )
    session.add(log)
    await session.flush()
    return log
