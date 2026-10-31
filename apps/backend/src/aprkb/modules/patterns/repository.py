"""Database queries for patterns and immutable version history."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
) -> list[PhrasePattern]:
    statement = select(PhrasePattern).join(Intent, Intent.id == PhrasePattern.intent_id)
    if intent_code:
        statement = statement.where(Intent.code == intent_code)
    if status:
        statement = statement.where(PhrasePattern.status == status)
    if section_code:
        version_ids = select(UsageConstraint.pattern_version_id).where(
            UsageConstraint.allowed_sections.contains([section_code])
        )
        statement = statement.where(PhrasePattern.current_version_id.in_(version_ids))
    statement = statement.order_by(PhrasePattern.created_at, PhrasePattern.id)
    statement = statement.offset(offset).limit(limit)
    return list(await session.scalars(statement))
