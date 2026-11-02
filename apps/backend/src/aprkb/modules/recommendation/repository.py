"""Database loading for preloaded recommendation views and result logs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.corpus.models import Article, License
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    UsageConstraint,
)
from aprkb.modules.recommendation.models import RecommendationLog
from aprkb.modules.taxonomy.models import Intent, Move, Step
from aprkb.shared.models import RefEnum

type PatternRow = tuple[
    PhrasePattern,
    Intent,
    PatternVersion,
    UsageConstraint | None,
    EvidenceProvenance | None,
    License | None,
    Article | None,
]


async def load_pattern_rows(
    session: AsyncSession,
    *,
    intent_code: str,
    query: str | None = None,
    move_code: str | None = None,
    claim_type: str | None = None,
) -> list[PatternRow]:
    """FR-07.1: retrieve DB-backed candidates; query is literal substring matching in this MVP."""
    # FR-07.2 gating happens in the pipeline after retrieval and before ranking
    # or returning any candidate.
    statement = (
        select(
            PhrasePattern,
            Intent,
            PatternVersion,
            UsageConstraint,
            EvidenceProvenance,
            License,
            Article,
        )
        .join(Intent, Intent.id == PhrasePattern.intent_id)
        .join(PatternVersion, PatternVersion.id == PhrasePattern.current_version_id)
        .outerjoin(UsageConstraint, UsageConstraint.pattern_version_id == PatternVersion.id)
        .outerjoin(EvidenceProvenance, EvidenceProvenance.pattern_version_id == PatternVersion.id)
        .outerjoin(License, License.id == EvidenceProvenance.license_id)
        .outerjoin(Article, Article.id == EvidenceProvenance.article_id)
        .where(Intent.code == intent_code)
        .order_by(PhrasePattern.created_at, PhrasePattern.id)
    )
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(
            PatternVersion.canonical_frame.ilike(f"%{escaped}%", escape="\\")
        )
    if move_code:
        statement = (
            statement.join(Step, Step.id == Intent.step_id)
            .join(Move, Move.id == Step.move_id)
            .where(Move.code == move_code)
        )
    if claim_type:
        statement = statement.where(PatternVersion.claim_type == claim_type)
    return list((await session.execute(statement)).unique().all())


async def reference_strengths(session: AsyncSession) -> list[RefEnum]:
    return list(
        await session.scalars(
            select(RefEnum).where(RefEnum.group == "epistemic_strength").order_by(RefEnum.order)
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
