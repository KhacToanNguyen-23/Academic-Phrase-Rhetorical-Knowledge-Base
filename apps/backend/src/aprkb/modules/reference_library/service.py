"""Reference-library query orchestration and response shaping."""

from collections import Counter, defaultdict

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.reference_library import repository
from aprkb.modules.reference_library.importer import NOTICE, SOURCE_URL
from aprkb.modules.reference_library.models import (
    ReferenceCategory,
    ReferenceEntry,
    ReferenceSource,
    ReferenceTaxonomyMap,
)
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


def _mapping_index(mappings: list[ReferenceTaxonomyMap]) -> dict[str, ReferenceTaxonomyMap]:
    return {mapping.reference_key: mapping for mapping in mappings}


def _category_read(
    category: ReferenceCategory,
    entry_count: int,
    mappings: list[ReferenceTaxonomyMap],
    heading_counts: Counter[int],
    intent_sections: dict[str, str],
) -> ReferenceCategoryRead:
    indexed = _mapping_index(mappings)
    category_mapping = indexed.get(f"category:{category.slug}")
    mapped_heading_positions = {
        mapping.heading_position
        for mapping in mappings
        if mapping.heading_position is not None and mapping.target_code is not None
    }
    mapped_entries = (
        entry_count
        if category_mapping is not None and category_mapping.target_code is not None
        else sum(heading_counts[position] for position in mapped_heading_positions)
    )
    mapped_section_positions = {
        mapping.heading_position
        for mapping in mappings
        if mapping.heading_position is not None
        and mapping.target_kind == "intent"
        and mapping.target_code in intent_sections
    }
    section_mapped_entries = (
        entry_count
        if category_mapping is not None and category_mapping.target_kind == "section"
        else sum(heading_counts[position] for position in mapped_section_positions)
    )
    intent_mapped_entries = sum(
        heading_counts[mapping.heading_position]
        for mapping in mappings
        if mapping.heading_position is not None and mapping.target_kind == "intent"
    )
    return ReferenceCategoryRead(
        slug=category.slug,
        title=category.title,
        kind=category.kind,  # type: ignore[arg-type]
        position=category.position,
        entry_count=entry_count,
        unmapped_entry_count=max(0, entry_count - mapped_entries),
        unmapped_section_entry_count=max(0, entry_count - section_mapped_entries),
        unmapped_intent_entry_count=max(0, entry_count - intent_mapped_entries),
        source_url=category.source_url,
        resolved_url=category.resolved_url,
        captured_at=category.captured_at,
        html_sha256=category.html_sha256,
        source_category=category.source_category,
        license_status=category.license_status,
        rights_status=category.rights_status,
        status=category.status,
        note=category.note,
        extraction_method=category.extraction_method,
        section_code=(
            category_mapping.target_code
            if category_mapping is not None and category_mapping.target_kind == "section"
            else None
        ),
        general_function_code=(
            category_mapping.target_code
            if category_mapping is not None and category_mapping.target_kind == "general_function"
            else None
        ),
        intent_codes=sorted(
            mapping.target_code
            for mapping in mappings
            if mapping.heading_position is not None
            and mapping.target_kind == "intent"
            and mapping.target_code is not None
        ),
        review_status=category_mapping.review_status if category_mapping else None,
    )


async def list_categories(session: AsyncSession) -> CategoryListResponse:
    source, rows = await repository.categories(session)
    category_ids = [category.id for category, _count in rows]
    mappings = await repository.mappings_for_categories(session, category_ids)
    entries = await repository.entries_for_categories(session, category_ids)
    intent_sections = await repository.intent_sections(session)
    mappings_by_category: dict[object, list[ReferenceTaxonomyMap]] = defaultdict(list)
    entries_by_category: dict[object, list[ReferenceEntry]] = defaultdict(list)
    for mapping in mappings:
        mappings_by_category[mapping.reference_category_id].append(mapping)
    for entry in entries:
        entries_by_category[entry.category_id].append(entry)
    return CategoryListResponse(
        source=source_notice(source) if source is not None else None,
        categories=[
            _category_read(
                category,
                count,
                mappings_by_category[category.id],
                Counter(entry.heading_position for entry in entries_by_category[category.id]),
                intent_sections,
            )
            for category, count in rows
        ],
    )


async def get_category(session: AsyncSession, slug: str) -> CategoryDetailResponse:
    found, entries, mappings = await repository.category_detail(session, slug)
    if found is None:
        raise HTTPException(status_code=404, detail="Reference category not found")
    category, source = found
    if source is None:
        raise HTTPException(status_code=404, detail="Reference category not found")
    indexed = _mapping_index(mappings)
    entries_by_heading: dict[int, list[ReferenceEntry]] = defaultdict(list)
    for entry in entries:
        entries_by_heading[entry.heading_position].append(entry)
    grouped = [
        HeadingGroup(
            heading=items[0].heading,
            heading_position=position,
            entries=[ReferenceEntryRead.model_validate(entry) for entry in items],
            intent_code=(
                heading_mapping.target_code
                if (heading_mapping := indexed.get(f"heading:{category.slug}:{position}"))
                is not None
                and heading_mapping.target_kind == "intent"
                else None
            ),
            review_status=(
                heading_mapping.review_status
                if (heading_mapping := indexed.get(f"heading:{category.slug}:{position}"))
                is not None
                else None
            ),
        )
        for position, items in entries_by_heading.items()
    ]
    heading_counts = Counter(entry.heading_position for entry in entries)
    intent_sections = await repository.intent_sections(session)
    return CategoryDetailResponse(
        source=source_notice(source),
        category=_category_read(category, len(entries), mappings, heading_counts, intent_sections),
        headings=grouped,
    )


async def search_entries(
    session: AsyncSession,
    query: str,
    category_slug: str | None,
    limit: int,
    *,
    section: str | None = None,
    intent: str | None = None,
    phrase_only: bool = False,
) -> SearchResponse:
    source, _ = await repository.categories(session)
    if source is None:
        return SearchResponse(source=None, query=query, results=[])
    # Taxonomy metadata is resolved below. Apply its predicates before the output cap.
    filtered = bool(section or intent or phrase_only)
    rows = await repository.search(session, query, category_slug, None if filtered else limit)
    category_ids = list({category.id for category, _entry in rows})
    mappings = await repository.mappings_for_categories(session, category_ids)
    intent_sections = await repository.intent_sections(session)
    mappings_by_category: dict[object, list[ReferenceTaxonomyMap]] = defaultdict(list)
    for mapping in mappings:
        mappings_by_category[mapping.reference_category_id].append(mapping)
    results: list[SearchResult] = []
    for category, entry in rows:
        if phrase_only and entry.kind != "phrase":
            continue
        indexed = _mapping_index(mappings_by_category[category.id])
        category_mapping = indexed.get(f"category:{category.slug}")
        heading_mapping = indexed.get(f"heading:{category.slug}:{entry.heading_position}")
        results.append(
            SearchResult(
                category_slug=category.slug,
                category_title=category.title,
                heading=entry.heading,
                entry=ReferenceEntryRead.model_validate(entry),
                section_code=(
                    intent_sections[heading_mapping.target_code]
                    if heading_mapping is not None
                    and heading_mapping.target_kind == "intent"
                    and heading_mapping.target_code in intent_sections
                    else category_mapping.target_code
                    if category_mapping is not None and category_mapping.target_kind == "section"
                    else None
                ),
                intent_code=(
                    heading_mapping.target_code
                    if heading_mapping is not None and heading_mapping.target_kind == "intent"
                    else None
                ),
                review_status=(
                    heading_mapping.review_status
                    if heading_mapping is not None
                    else category_mapping.review_status
                    if category_mapping is not None
                    else None
                ),
            )
        )
    results = [
        item
        for item in results
        if (section is None or item.section_code == section)
        and (intent is None or item.intent_code == intent)
    ][:limit]
    return SearchResponse(source=source_notice(source), query=query, results=results)
