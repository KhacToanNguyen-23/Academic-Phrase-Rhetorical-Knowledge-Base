"""Database queries scoped to the reference-library tables only."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.reference_library.models import (
    ReferenceCategory,
    ReferenceEntry,
    ReferenceSource,
    ReferenceTaxonomyMap,
)
from aprkb.modules.taxonomy.models import Intent, Move, Section, Step, TaxonomyRelease


async def categories(
    session: AsyncSession,
) -> tuple[ReferenceSource | None, list[tuple[ReferenceCategory, int]]]:
    source = await session.scalar(
        select(ReferenceSource).order_by(ReferenceSource.imported_at.desc()).limit(1)
    )
    if source is None:
        return None, []
    rows = await session.execute(
        select(ReferenceCategory, func.count(ReferenceEntry.id))
        .outerjoin(ReferenceEntry, ReferenceEntry.category_id == ReferenceCategory.id)
        .where(ReferenceCategory.source_id == source.id)
        .group_by(ReferenceCategory.id)
        .order_by(ReferenceCategory.position)
    )
    return source, [(category, count) for category, count in rows]


async def category_detail(
    session: AsyncSession, slug: str
) -> tuple[
    tuple[ReferenceCategory, ReferenceSource | None] | None,
    list[ReferenceEntry],
    list[ReferenceTaxonomyMap],
]:
    source = await session.scalar(
        select(ReferenceSource).order_by(ReferenceSource.imported_at.desc()).limit(1)
    )
    if source is None:
        return None, [], []
    category = await session.scalar(
        select(ReferenceCategory).where(
            ReferenceCategory.source_id == source.id, ReferenceCategory.slug == slug
        )
    )
    if category is None:
        return None, [], []
    entries = list(
        await session.scalars(
            select(ReferenceEntry)
            .where(ReferenceEntry.category_id == category.id)
            .order_by(ReferenceEntry.heading_position, ReferenceEntry.position)
        )
    )
    mappings = list(
        await session.scalars(
            select(ReferenceTaxonomyMap)
            .where(ReferenceTaxonomyMap.reference_category_id == category.id)
            .order_by(ReferenceTaxonomyMap.reference_key)
        )
    )
    return (category, source), entries, mappings


async def mappings_for_categories(
    session: AsyncSession, category_ids: list[UUID]
) -> list[ReferenceTaxonomyMap]:
    if not category_ids:
        return []
    return list(
        await session.scalars(
            select(ReferenceTaxonomyMap)
            .where(ReferenceTaxonomyMap.reference_category_id.in_(category_ids))
            .order_by(
                ReferenceTaxonomyMap.reference_category_id, ReferenceTaxonomyMap.reference_key
            )
        )
    )


async def entries_for_categories(
    session: AsyncSession, category_ids: list[UUID]
) -> list[ReferenceEntry]:
    if not category_ids:
        return []
    return list(
        await session.scalars(
            select(ReferenceEntry)
            .where(ReferenceEntry.category_id.in_(category_ids))
            .order_by(ReferenceEntry.category_id, ReferenceEntry.position)
        )
    )


async def intent_sections(session: AsyncSession) -> dict[str, str]:
    release_id = await session.scalar(
        select(TaxonomyRelease.id)
        .where(TaxonomyRelease.status == "published")
        .order_by(TaxonomyRelease.published_at.desc(), TaxonomyRelease.version.desc())
        .limit(1)
    )
    if release_id is None:
        return {}
    rows = await session.execute(
        select(Intent.code, Section.code)
        .join(Step, Intent.step_id == Step.id)
        .join(Move, Step.move_id == Move.id)
        .join(Section, Move.section_id == Section.id)
        .where(Section.release_id == release_id)
    )
    return {intent_code: section_code for intent_code, section_code in rows}


async def search(
    session: AsyncSession, query: str, category_slug: str | None, limit: int | None
) -> list[tuple[ReferenceCategory, ReferenceEntry]]:
    source = await session.scalar(
        select(ReferenceSource).order_by(ReferenceSource.imported_at.desc()).limit(1)
    )
    if source is None:
        return []
    statement = (
        select(ReferenceCategory, ReferenceEntry)
        .join(ReferenceEntry, ReferenceEntry.category_id == ReferenceCategory.id)
        .where(ReferenceCategory.source_id == source.id)
    )
    if category_slug:
        statement = statement.where(ReferenceCategory.slug == category_slug)
    terms = func.plainto_tsquery("simple", query)
    full_text = func.to_tsvector("simple", ReferenceEntry.search_text).op("@@")(terms)
    if len(query.strip()) < 3:
        statement = statement.where(ReferenceEntry.search_text.ilike(f"%{query}%", escape="\\"))
    else:
        statement = statement.where(
            or_(full_text, ReferenceEntry.search_text.ilike(f"%{query}%", escape="\\"))
        )
    return list(
        await session.execute(
            statement.order_by(
                ReferenceCategory.position, ReferenceEntry.position, ReferenceEntry.id
            ).limit(limit)
        )
    )
