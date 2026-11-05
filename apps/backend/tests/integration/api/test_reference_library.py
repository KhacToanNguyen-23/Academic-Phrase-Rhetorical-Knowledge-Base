"""PostgreSQL API/import isolation tests use invented fixture text only."""

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.config import settings
from aprkb.core.deps import get_db_session
from aprkb.modules.audit.models import AuditEvent
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.reference_library.importer import import_library, parse_document, purge_library
from aprkb.modules.reference_library.mapping import export_template, import_mapping_file
from aprkb.modules.reference_library.models import (
    ReferenceCategory,
    ReferenceEntry,
    ReferenceSource,
    ReferenceTaxonomyMap,
)
from aprkb.seeds.load import run_seed


@pytest_asyncio.fixture
async def session_factory(
    postgres_test_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker]:
    yield async_sessionmaker(postgres_test_engine, expire_on_commit=False)


def fixture_library():
    pages = []
    for title, slug, paragraph in (
        ("Introducing work", "introducing-work", "Alpha beta gamma"),
        ("Giving examples", "giving-examples", "Delta epsilon"),
    ):
        blocks = [
            {"block_id": "p1", "heading": title, "kind": "paragraph", "lines": [paragraph]},
            {
                "block_id": "p2",
                "heading": "Secondary heading",
                "kind": "table",
                "rows": [["Alpha", "beta", "gamma"]],
            },
            {
                "block_id": "p3",
                "heading": "Secondary heading",
                "kind": "paragraph",
                "lines": ["Delta epsilon"],
            },
            {
                "block_id": "p4",
                "heading": "Secondary heading",
                "kind": "table",
                "rows": [["zeta", "eta"]],
            },
        ]
        pages.append(
            {
                "title": title,
                "source_url": f"https://example.test/{slug}/",
                "resolved_url": f"https://example.test/{slug}/",
                "captured_at": "2026-01-01",
                "html_sha256": "f" * 64,
                "source_category": "external_reference",
                "license_status": "unknown",
                "rights_status": "unverified",
                "status": "quarantined",
                "note": "Fixture only",
                "blocks": blocks,
            }
        )
    payload = {
        "source": "Example University Phrase Library",
        "status": "quarantined",
        "license_status": "unknown",
        "page_count": 2,
        "block_count": 8,
        "table_count": 4,
        "pages": pages,
    }
    raw = json.dumps(payload).encode()
    return parse_document(payload, raw)


@pytest_asyncio.fixture
async def api_client(
    session_factory: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    monkeypatch.setattr(settings, "reference_library_enabled", True)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client,
    ):
        yield client


async def _client_key(session_factory: async_sessionmaker) -> str:
    async with session_factory() as session:
        client, key = await create_api_key(session, name="reference reader", role="client")
        await session.commit()
    return key


@pytest.mark.asyncio
async def test_reference_search_filters_mapped_hits_after_old_50_cap(api_client, session_factory):
    async with session_factory() as session:
        await run_seed(session)
        await session.commit()
        await import_library(session, fixture_library(), request_id="late-match-import")
        category = await session.scalar(
            select(ReferenceCategory).where(ReferenceCategory.slug == "introducing-work")
        )
        assert category is not None
        session.add(
            ReferenceTaxonomyMap(
                reference_category_id=category.id,
                reference_key="heading:introducing-work:99",
                reference_title="Late mapped heading",
                heading_position=99,
                target_kind="intent",
                target_code="DISCUSSION_FINDING",
                review_status="approved",
            )
        )
        for index in range(51):
            session.add(
                ReferenceEntry(
                    category_id=category.id,
                    heading="Invented boundary heading",
                    heading_position=99 if index == 50 else 98,
                    block_index=100 + index,
                    block_id=f"boundary-{index}",
                    kind="phrase",
                    text=None,
                    cells=[[f"Boundaryneedle phrase {index}"]],
                    search_text=f"Boundaryneedle phrase {index}",
                    position=100 + index,
                )
            )
        await session.commit()
    key = await _client_key(session_factory)
    response = await api_client.get(
        "/v1/reference-library/search",
        headers={"X-API-Key": key},
        params={
            "q": "Boundaryneedle",
            "section": "DISCUSSION",
            "intent": "DISCUSSION_FINDING",
            "phrase_only": True,
            "limit": 1,
        },
    )
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["entry"]["position"] == 150
    assert results[0]["section_code"] == "DISCUSSION"
    assert results[0]["intent_code"] == "DISCUSSION_FINDING"


@pytest.mark.asyncio
async def test_reference_import_replace_purge_and_read_api(api_client, session_factory, tmp_path):
    library = fixture_library()
    async with session_factory() as session:
        counts = await import_library(session, library, request_id="test-import")
    async with session_factory() as session:
        repeated = await import_library(session, library, request_id="test-import-again")
        assert repeated == counts
        assert await session.scalar(select(func.count()).select_from(ReferenceSource)) == 1
        assert await session.scalar(select(func.count()).select_from(ReferenceCategory)) == 2
        assert await session.scalar(select(func.count()).select_from(ReferenceEntry)) == 8
        events = list(
            await session.scalars(
                select(AuditEvent).where(AuditEvent.action == "reference_library.import")
            )
        )
        assert len(events) == 2
        assert "Alpha beta gamma" not in repr([event.after for event in events])

    async with session_factory() as session:
        await run_seed(session)
        await session.commit()
    async with session_factory() as session:
        template = await export_template(session)
        assert "Secondary heading" in template
        assert "Alpha beta gamma" not in template
    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "reference_key": "heading:introducing-work:1",
                        "reference_title": "Secondary heading",
                        "target_kind": "intent",
                        "target_code": "DISCUSSION_FINDING",
                        "review_status": "proposed",
                        "mapped_by": "fixture-owner",
                        "note": "Fixture mapping",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    async with session_factory() as session:
        assert await import_mapping_file(session, mapping_path) == 1
    async with session_factory() as session:
        await import_library(session, library, request_id="test-import-after-map")
    async with session_factory() as session:
        assert await import_mapping_file(session, mapping_path) == 1
    invalid_mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    invalid_mapping["mappings"][0]["target_code"] = "UNKNOWN_CODE"
    mapping_path.write_text(json.dumps(invalid_mapping), encoding="utf-8")
    async with session_factory() as session:
        with pytest.raises(ValueError, match="Unknown intent taxonomy code"):
            await import_mapping_file(session, mapping_path)
        await session.rollback()

    key = await _client_key(session_factory)
    headers = {"X-API-Key": key}
    categories = await api_client.get("/v1/reference-library/categories", headers=headers)
    assert categories.status_code == 200
    assert categories.json()["source"]["notice"].startswith("Source: University of Manchester")
    assert [item["slug"] for item in categories.json()["categories"]] == [
        "introducing-work",
        "giving-examples",
    ]
    assert categories.json()["categories"][0]["section_code"] == "INTRO"
    assert categories.json()["categories"][0]["review_status"] == "proposed"
    assert (
        categories.json()["categories"][0]["resolved_url"]
        == "https://example.test/introducing-work/"
    )
    assert categories.json()["categories"][0]["captured_at"] == "2026-01-01"
    assert categories.json()["categories"][0]["html_sha256"] == "f" * 64
    assert categories.json()["categories"][0]["source_category"] == "external_reference"
    assert categories.json()["categories"][0]["license_status"] == "unknown"
    assert categories.json()["categories"][0]["rights_status"] == "unverified"
    assert categories.json()["categories"][0]["status"] == "quarantined"
    assert categories.json()["categories"][0]["note"] == "Fixture only"
    assert categories.json()["categories"][0]["extraction_method"] is None
    assert categories.json()["categories"][1]["section_code"] is None
    assert categories.json()["categories"][1]["review_status"] is None
    detail = await api_client.get(
        "/v1/reference-library/categories/introducing-work", headers=headers
    )
    assert detail.status_code == 200
    assert [group["heading"] for group in detail.json()["headings"]] == [
        "Introducing work",
        "Secondary heading",
    ]
    secondary_entries = detail.json()["headings"][1]["entries"]
    assert detail.json()["headings"][1]["intent_code"] == "DISCUSSION_FINDING"
    assert detail.json()["headings"][1]["review_status"] == "proposed"
    assert detail.json()["headings"][0]["intent_code"] is None
    assert detail.json()["headings"][0]["review_status"] is None
    assert [entry["kind"] for entry in secondary_entries] == ["phrase", "note", "phrase"]
    assert [entry["block_index"] for entry in secondary_entries] == [1, 2, 3]
    assert [entry["block_id"] for entry in secondary_entries] == ["p2", "p3", "p4"]
    assert secondary_entries[0]["cells"] == [["Alpha"], ["beta"], ["gamma"]]
    assert secondary_entries[2]["cells"] == [["zeta"], ["eta"]]
    hit = await api_client.get("/v1/reference-library/search", params={"q": "Al"}, headers=headers)
    miss = await api_client.get(
        "/v1/reference-library/search", params={"q": "no-match"}, headers=headers
    )
    assert [(item["category_slug"], item["heading"]) for item in hit.json()["results"]] == [
        ("introducing-work", "Introducing work"),
        ("introducing-work", "Secondary heading"),
        ("giving-examples", "Secondary heading"),
    ]
    assert hit.json()["results"][0]["section_code"] == "INTRO"
    assert hit.json()["results"][1]["intent_code"] == "DISCUSSION_FINDING"
    assert hit.json()["results"][1]["section_code"] == "DISCUSSION"
    assert miss.json()["results"] == []

    async with session_factory() as session:
        stale_source = ReferenceSource(
            name="Older fixture source",
            source_url="https://example.test/older/",
            license_status="fixture",
            rights_status="fixture",
            status="fixture",
            content_sha256="a" * 64,
            imported_at=datetime(2000, 1, 1, tzinfo=UTC),
        )
        session.add(stale_source)
        await session.flush()
        stale_category = ReferenceCategory(
            source_id=stale_source.id,
            slug="introducing-work",
            title="Stale category title",
            kind="section",
            position=0,
            source_url="https://example.test/older/introducing-work/",
            resolved_url="https://example.test/older/introducing-work/",
            captured_at="2000-01-01",
            html_sha256="b" * 64,
            source_category="fixture",
            license_status="fixture",
            rights_status="fixture",
            status="fixture",
            note="Stale fixture note",
        )
        session.add(stale_category)
        await session.flush()
        session.add(
            ReferenceEntry(
                category_id=stale_category.id,
                heading="Stale heading",
                heading_position=0,
                block_index=0,
                block_id="stale-0",
                kind="phrase",
                text=None,
                cells=[["Stale only token"], ["invented fixture"]],
                search_text="Stale only token invented fixture",
                position=0,
            )
        )
        await session.commit()
    active_detail = await api_client.get(
        "/v1/reference-library/categories/introducing-work", headers=headers
    )
    stale_hit = await api_client.get(
        "/v1/reference-library/search",
        params={"q": "Stale only token"},
        headers=headers,
    )
    assert active_detail.json()["category"]["title"] == "Introducing work"
    assert stale_hit.json()["results"] == []

    patterns = await api_client.get("/v1/patterns", headers=headers)
    assert "Alpha beta gamma" not in patterns.text
    # Recommendations need approved authored patterns; reference data stays isolated.
    recommendation = await api_client.post(
        "/v1/recommendations",
        headers=headers,
        json={"intent": "INTRO_GAP_INDICATE", "section": "INTRO", "query": "Alpha beta gamma"},
    )
    assert recommendation.status_code == 200
    assert "Alpha beta gamma" not in recommendation.text

    async with session_factory() as session:
        assert await purge_library(session, request_id="test-purge") == 2
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ReferenceCategory)) == 0
    empty_categories = await api_client.get("/v1/reference-library/categories", headers=headers)
    empty_search = await api_client.get(
        "/v1/reference-library/search", params={"q": "Alpha"}, headers=headers
    )
    patterns_after_purge = await api_client.get("/v1/patterns", headers=headers)
    assert empty_categories.status_code == 200
    assert empty_categories.json() == {"source": None, "categories": []}
    assert empty_search.status_code == 200
    assert empty_search.json()["results"] == []
    assert patterns_after_purge.status_code == 200


@pytest.mark.asyncio
async def test_reference_routes_return_standard_404_when_flag_is_off(api_client, monkeypatch):
    monkeypatch.setattr(settings, "reference_library_enabled", False)
    response = await api_client.get("/v1/reference-library/categories")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
