"""Database queries for patterns and immutable version history."""

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.corpus.models import License
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    UsageConstraint,
)
from aprkb.modules.taxonomy.models import Intent


async def get_pattern(session: AsyncSession, pattern_id: UUID) -> PhrasePattern | None:
    return await session.get(PhrasePattern, pattern_id)


async def get_intent(session: AsyncSession, code: str) -> Intent | None:
    return await session.scalar(select(Intent).where(Intent.code == code))


async def get_current_version(
    session: AsyncSession, pattern: PhrasePattern
) -> PatternVersion | None:
    if pattern.current_version_id is None:
        return None
    return await session.get(PatternVersion, pattern.current_version_id)


async def get_usage_constraint(session: AsyncSession, version_id: UUID) -> UsageConstraint | None:
    return await session.scalar(
        select(UsageConstraint).where(UsageConstraint.pattern_version_id == version_id)
    )


async def get_provenance(session: AsyncSession, version_id: UUID) -> EvidenceProvenance | None:
    return await session.scalar(
        select(EvidenceProvenance)
        .where(EvidenceProvenance.pattern_version_id == version_id)
        .order_by(EvidenceProvenance.created_at)
    )


async def list_provenances(session: AsyncSession, version_id: UUID) -> list[EvidenceProvenance]:
    return list(
        await session.scalars(
            select(EvidenceProvenance).where(EvidenceProvenance.pattern_version_id == version_id)
        )
    )


async def list_versions(session: AsyncSession, pattern_id: UUID) -> list[PatternVersion]:
    return list(
        await session.scalars(
            select(PatternVersion)
            .where(PatternVersion.pattern_id == pattern_id)
            .order_by(PatternVersion.version_no)
        )
    )


async def list_patterns(
    session: AsyncSession,
    *,
    intent_code: str | None,
    section_code: str | None,
    status: str | None,
    offset: int,
    limit: int,
    renderable_only: bool = False,
) -> list[tuple[PhrasePattern, Intent, PatternVersion | None, UsageConstraint | None]]:
    statement = (
        select(PhrasePattern, Intent, PatternVersion, UsageConstraint)
        .join(Intent, Intent.id == PhrasePattern.intent_id)
        .outerjoin(PatternVersion, PatternVersion.id == PhrasePattern.current_version_id)
        .outerjoin(UsageConstraint, UsageConstraint.pattern_version_id == PatternVersion.id)
    )
    if intent_code:
        statement = statement.where(Intent.code == intent_code)
    if status:
        statement = statement.where(PhrasePattern.status == status)
    if section_code:
        statement = statement.where(UsageConstraint.allowed_sections.contains([section_code]))
    if renderable_only:
        single_provenance_versions = (
            select(EvidenceProvenance.pattern_version_id)
            .group_by(EvidenceProvenance.pattern_version_id)
            .having(func.count(EvidenceProvenance.id) == 1)
        )
        statement = (
            statement.join(
                EvidenceProvenance,
                EvidenceProvenance.pattern_version_id == PatternVersion.id,
            )
            .outerjoin(License, License.id == EvidenceProvenance.license_id)
            .where(
                PhrasePattern.status == "approved",
                PatternVersion.id.in_(single_provenance_versions),
                or_(
                    EvidenceProvenance.source_type == "authored",
                    and_(
                        EvidenceProvenance.source_type == "mined",
                        License.allows_display.is_(True),
                    ),
                ),
            )
        )
    statement = statement.order_by(PhrasePattern.created_at, PhrasePattern.id)
    statement = statement.offset(offset).limit(limit)
    result = await session.execute(statement)
    return [(pattern, intent, version, usage) for pattern, intent, version, usage in result]
