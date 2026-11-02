"""Reference-library query orchestration and response shaping."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.reference_library import repository
from aprkb.modules.reference_library.importer import NOTICE, SOURCE_URL
from aprkb.modules.reference_library.models import ReferenceSource
from aprkb.modules.reference_library.schemas import (
    CategoryDetailResponse,
    CategoryListResponse,
    HeadingGroup,
    ReferenceCategoryRead,
    ReferenceEntryRead,
    SearchResponse,
    SearchResult,
    SourceNotice,
)


def source_notice(source: ReferenceSource) -> SourceNotice:
    return SourceNotice(
        name=source.name,
        url=SOURCE_URL,
        license_status=source.license_status,
        rights_status=source.rights_status,
        notice=NOTICE,
    )


async def list_categories(session: AsyncSession) -> CategoryListResponse:
    source, rows = await repository.categories(session)
    if source is None:
        raise HTTPException(status_code=404, detail="Reference library has not been imported")
    return CategoryListResponse(
        source=source_notice(source),
        categories=[
            ReferenceCategoryRead(
                slug=row.slug,
                title=row.title,
                kind=row.kind,  # type: ignore[arg-type]
                position=row.position,
                entry_count=count,
            )
            for row, count in rows
        ],
    )


async def get_category(session: AsyncSession, slug: str) -> CategoryDetailResponse:
    found, entries = await repository.category_detail(session, slug)
    if found is None:
        raise HTTPException(status_code=404, detail="Reference category not found")
    category, source = found
    if source is None:
        raise HTTPException(status_code=404, detail="Reference category not found")
    grouped: list[HeadingGroup] = []
    for entry in entries:
        if not grouped or grouped[-1].heading_position != entry.heading_position:
            grouped.append(
                HeadingGroup(
                    heading=entry.heading, heading_position=entry.heading_position, entries=[]
                )
            )
        grouped[-1].entries.append(ReferenceEntryRead.model_validate(entry))
    return CategoryDetailResponse(
        source=source_notice(source),
        category=ReferenceCategoryRead(
            slug=category.slug,
            title=category.title,
            kind=category.kind,  # type: ignore[arg-type]
            position=category.position,
            entry_count=len(entries),
        ),
        headings=grouped,
    )


async def search_entries(
    session: AsyncSession, query: str, category_slug: str | None, limit: int
) -> SearchResponse:
    source, _ = await repository.categories(session)
    if source is None:
        raise HTTPException(status_code=404, detail="Reference library has not been imported")
    rows = await repository.search(session, query, category_slug, limit)
    return SearchResponse(
        source=source_notice(source),
        query=query,
        results=[
            SearchResult(
                category_slug=category.slug,
                category_title=category.title,
                heading=entry.heading,
                entry=ReferenceEntryRead.model_validate(entry),
            )
            for category, entry in rows
        ],
    )
