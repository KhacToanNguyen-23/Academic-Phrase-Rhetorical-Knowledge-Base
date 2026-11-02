"""PostgreSQL API/import isolation tests use invented fixture text only."""

import json
from collections.abc import AsyncIterator

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
from aprkb.modules.reference_library.models import (
    ReferenceCategory,
    ReferenceEntry,
    ReferenceSource,
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
        "block_count": 4,
        "table_count": 2,
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
async def test_reference_import_replace_purge_and_read_api(api_client, session_factory):
    library = fixture_library()
    async with session_factory() as session:
        counts = await import_library(session, library, request_id="test-import")
    async with session_factory() as session:
        repeated = await import_library(session, library, request_id="test-import-again")
        assert repeated == counts
        assert await session.scalar(select(func.count()).select_from(ReferenceSource)) == 1
        assert await session.scalar(select(func.count()).select_from(ReferenceCategory)) == 2
        assert await session.scalar(select(func.count()).select_from(ReferenceEntry)) == 4
        events = list(
            await session.scalars(
                select(AuditEvent).where(AuditEvent.action == "reference_library.import")
            )
        )
        assert len(events) == 2
        assert "Alpha beta gamma" not in repr([event.after for event in events])

    key = await _client_key(session_factory)
    headers = {"X-API-Key": key}
    categories = await api_client.get("/v1/reference-library/categories", headers=headers)
    assert categories.status_code == 200
    assert categories.json()["source"]["notice"].startswith("Source: University of Manchester")
    assert [item["slug"] for item in categories.json()["categories"]] == [
        "introducing-work",
        "giving-examples",
    ]
    detail = await api_client.get(
        "/v1/reference-library/categories/introducing-work", headers=headers
    )
    assert detail.status_code == 200
    assert [group["heading"] for group in detail.json()["headings"]] == [
        "Introducing work",
        "Secondary heading",
    ]
    assert detail.json()["headings"][1]["entries"][0]["cells"] == [["Alpha"], ["beta"], ["gamma"]]
    hit = await api_client.get("/v1/reference-library/search", params={"q": "Al"}, headers=headers)
    miss = await api_client.get(
        "/v1/reference-library/search", params={"q": "no-match"}, headers=headers
    )
    assert [(item["category_slug"], item["heading"]) for item in hit.json()["results"]] == [
        ("introducing-work", "Introducing work"),
        ("introducing-work", "Secondary heading"),
        ("giving-examples", "Secondary heading"),
    ]
    assert miss.json()["results"] == []
    patterns = await api_client.get("/v1/patterns", headers=headers)
    assert "Alpha beta gamma" not in patterns.text
    # Recommendations need the reference data and approved authored patterns.
    async with session_factory() as session:
        await run_seed(session)
        await session.commit()
    recommendation = await api_client.post(
        "/v1/recommendations",
        headers=headers,
        json={"intent": "INTRO_GAP_INDICATE", "section": "INTRO", "query": "Alpha beta gamma"},
    )
    assert recommendation.status_code == 200
    assert "Alpha beta gamma" not in recommendation.text

    async with session_factory() as session:
        assert await purge_library(session, request_id="test-purge") == 1
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ReferenceCategory)) == 0


@pytest.mark.asyncio
async def test_reference_routes_return_standard_404_when_flag_is_off(api_client, monkeypatch):
    monkeypatch.setattr(settings, "reference_library_enabled", False)
    response = await api_client.get("/v1/reference-library/categories")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
