"""Search limits must apply after mapping and phrase eligibility."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from aprkb.modules.reference_library import repository, service
from aprkb.modules.reference_library.models import (
    ReferenceCategory,
    ReferenceEntry,
    ReferenceSource,
    ReferenceTaxonomyMap,
)


@pytest.mark.parametrize(
    "section,intent,expected_heading",
    [("RESULTS", "REPORT", 51), ("INTRO", None, 0), ("RESULTS", "UNKNOWN", None)],
)
async def test_search_maps_all_hits_before_section_intent_and_limit(
    monkeypatch, section, intent, expected_heading
):
    category = ReferenceCategory(id=uuid4(), slug="fixture", title="Invented category")
    source = ReferenceSource(
        name="Invented source", license_status="unknown", rights_status="unverified"
    )
    entries = [
        ReferenceEntry(
            id=uuid4(),
            heading=f"Heading {index}",
            heading_position=index,
            block_index=index,
            block_id=f"block-{index}",
            kind="phrase",
            text=None,
            cells=[["Invented result"]],
            position=index,
        )
        for index in range(53)
    ]
    # A matching note must not consume the phrase-only output cap.
    entries[50].kind = "note"
    entries[50].text = "Invented note"
    entries[50].cells = None
    mappings = [
        ReferenceTaxonomyMap(
            reference_category_id=category.id,
            reference_key="category:fixture",
            target_kind="section",
            target_code="INTRO",
            review_status="proposed",
        ),
        *[
            ReferenceTaxonomyMap(
                reference_category_id=category.id,
                reference_key=f"heading:fixture:{index}",
                target_kind="intent",
                target_code="REPORT",
                review_status="approved",
            )
            for index in (50, 51, 52)
        ],
    ]
    monkeypatch.setattr(repository, "categories", AsyncMock(return_value=(source, [])))
    search = AsyncMock(return_value=[(category, entry) for entry in entries])
    monkeypatch.setattr(repository, "search", search)
    monkeypatch.setattr(repository, "mappings_for_categories", AsyncMock(return_value=mappings))
    monkeypatch.setattr(
        repository, "intent_sections", AsyncMock(return_value={"REPORT": "RESULTS"})
    )

    result = await service.search_entries(
        AsyncMock(), "invented", None, 1, section=section, intent=intent, phrase_only=True
    )

    assert [item.entry.heading_position for item in result.results] == (
        [] if expected_heading is None else [expected_heading]
    )
    assert search.await_args.args[-1] is None
    if expected_heading == 51:
        assert result.results[0].section_code == "RESULTS"
        assert result.results[0].intent_code == "REPORT"


async def test_phrase_only_search_excludes_notes_before_limit_without_taxonomy_filters(monkeypatch):
    category = ReferenceCategory(id=uuid4(), slug="fixture", title="Invented category")
    source = ReferenceSource(
        name="Invented source", license_status="unknown", rights_status="unverified"
    )
    entries = [
        ReferenceEntry(
            id=uuid4(),
            heading="Heading",
            heading_position=0,
            block_index=index,
            block_id=index,
            kind="note" if index < 50 else "phrase",
            text="Invented note" if index < 50 else None,
            cells=None if index < 50 else [["Invented phrase"]],
            position=index,
        )
        for index in range(51)
    ]
    monkeypatch.setattr(repository, "categories", AsyncMock(return_value=(source, [])))
    monkeypatch.setattr(
        repository, "search", AsyncMock(return_value=[(category, e) for e in entries])
    )
    monkeypatch.setattr(repository, "mappings_for_categories", AsyncMock(return_value=[]))
    monkeypatch.setattr(repository, "intent_sections", AsyncMock(return_value={}))

    result = await service.search_entries(AsyncMock(), "invented", None, 1, phrase_only=True)

    assert [item.entry.position for item in result.results] == [50]
    assert result.results[0].section_code is None
