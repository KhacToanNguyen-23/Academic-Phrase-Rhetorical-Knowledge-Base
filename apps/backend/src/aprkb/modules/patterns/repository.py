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
from aprkb.modules.taxonomy.models import Intent, Move, Section, Step, TaxonomyRelease


async def get_pattern(session: AsyncSession, pattern_id: UUID) -> PhrasePattern | None:
    return await session.get(PhrasePattern, pattern_id)


async def get_intent(session: AsyncSession, code: str) -> Intent | None:
    return await session.scalar(
        select(Intent)
        .join(Step, Step.id == Intent.step_id)
        .join(Move, Move.id == Step.move_id)
        .join(Section, Section.id == Move.section_id)
        .join(TaxonomyRelease, TaxonomyRelease.id == Section.release_id)
        .where(Intent.code == code, TaxonomyRelease.status == "published")
        .order_by(TaxonomyRelease.published_at.desc(), TaxonomyRelease.version.desc())
        .limit(1)
    )


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
