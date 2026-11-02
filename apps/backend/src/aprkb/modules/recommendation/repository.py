"""Database loading for preloaded recommendation views and result logs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.corpus.models import License
from aprkb.modules.journals.models import JournalProfile
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    UsageConstraint,
)
from aprkb.modules.recommendation.models import RecommendationLog
from aprkb.modules.taxonomy.models import Intent
from aprkb.shared.models import RefEnum

type PatternRow = tuple[
    PhrasePattern,
    Intent,
    PatternVersion,
    UsageConstraint | None,
    EvidenceProvenance | None,
    License | None,
]


async def load_pattern_rows(session: AsyncSession, *, intent_code: str) -> list[PatternRow]:
    statement = (
        select(PhrasePattern, Intent, PatternVersion, UsageConstraint, EvidenceProvenance, License)
        .join(Intent, Intent.id == PhrasePattern.intent_id)
        .join(PatternVersion, PatternVersion.id == PhrasePattern.current_version_id)
        .outerjoin(UsageConstraint, UsageConstraint.pattern_version_id == PatternVersion.id)
        .outerjoin(EvidenceProvenance, EvidenceProvenance.pattern_version_id == PatternVersion.id)
        .outerjoin(License, License.id == EvidenceProvenance.license_id)
        .where(Intent.code == intent_code)
        .order_by(PhrasePattern.created_at, PhrasePattern.id)
    )
    rows = (await session.execute(statement)).unique().all()
    return [(row[0], row[1], row[2], row[3], row[4], row[5]) for row in rows]


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


async def get_journal(session: AsyncSession, journal_id: UUID | None) -> JournalProfile | None:
    if journal_id is None:
        return None
    return await session.get(JournalProfile, journal_id)
