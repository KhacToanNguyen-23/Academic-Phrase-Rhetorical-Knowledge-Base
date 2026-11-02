"""Database queries scoped to the reference-library tables only."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.reference_library.models import (
    ReferenceCategory,
    ReferenceEntry,
    ReferenceSource,
)


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
) -> tuple[tuple[ReferenceCategory, ReferenceSource | None] | None, list[ReferenceEntry]]:
    category = await session.scalar(select(ReferenceCategory).where(ReferenceCategory.slug == slug))
    if category is None:
        return None, []
    source = await session.get(ReferenceSource, category.source_id)
    entries = list(
        await session.scalars(
            select(ReferenceEntry)
            .where(ReferenceEntry.category_id == category.id)
            .order_by(ReferenceEntry.heading_position, ReferenceEntry.position)
        )
    )
    return (category, source), entries


async def search(
    session: AsyncSession, query: str, category_slug: str | None, limit: int
) -> list[tuple[ReferenceCategory, ReferenceEntry]]:
    statement = select(ReferenceCategory, ReferenceEntry).join(
        ReferenceEntry, ReferenceEntry.category_id == ReferenceCategory.id
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
            statement.order_by(ReferenceCategory.position, ReferenceEntry.position).limit(limit)
        )
    )
