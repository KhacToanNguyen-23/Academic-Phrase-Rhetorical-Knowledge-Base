"""Academic Phrase Bank persistence, taxonomy mapping, and read API checks."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.deps import get_db_session
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.patterns.models import PatternVersion, PhrasePattern
from aprkb.seeds.load import run_seed
from tests.seed_data import seed_legacy_pattern_fixtures


@pytest_asyncio.fixture
async def session_factory(postgres_test_engine: AsyncEngine) -> AsyncIterator[async_sessionmaker]:
    yield async_sessionmaker(postgres_test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def api_client(session_factory: async_sessionmaker) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client,
    ):
        yield client


async def _create_key(session_factory: async_sessionmaker, role: str) -> tuple[ApiClient, str]:
    async with session_factory() as session:
        client, key = await create_api_key(session, name=f"APB {role}", role=role)
        await session.commit()
        return client, key


async def _seed(session_factory: async_sessionmaker) -> None:
    async with session_factory() as session:
        await run_seed(session)
        await seed_legacy_pattern_fixtures(session)
        await session.commit()


async def _pattern_version(session_factory: async_sessionmaker, frame: str) -> PatternVersion:
    async with session_factory() as session:
        pattern = await session.scalar(
            select(PhrasePattern)
            .join(PatternVersion, PatternVersion.id == PhrasePattern.current_version_id)
            .where(PatternVersion.canonical_frame == frame)
        )
        assert pattern is not None and pattern.current_version_id is not None
        version = await session.get(PatternVersion, pattern.current_version_id)
        assert version is not None
        return version


@pytest.mark.asyncio
async def test_function_catalog_is_seeded_and_versioned(api_client, session_factory):
    await _seed(session_factory)
    _, key = await _create_key(session_factory, "client")

    response = await api_client.get("/v1/academic-phrases/functions", headers={"X-API-Key": key})

    assert response.status_code == 200
    options = {item["code"]: item for item in response.json()["items"]}
    assert options["INDICATE_GAP"]["family_code"] == "IDENTIFYING_NICHE"
    assert options["INDICATE_GAP"]["version"] == "1.0.0"
    assert options["INDICATE_GAP"]["status"] == "proposed"


@pytest.mark.asyncio
async def test_curator_links_apb_metadata_to_database_taxonomy_and_clients_filter_it(
    api_client, session_factory
):
    await _seed(session_factory)
    _, curator_key = await _create_key(session_factory, "curator")
    _, client_key = await _create_key(session_factory, "client")
    version = await _pattern_version(
        session_factory, "The role of {topic} in {context} remains underexplored."
    )
    payload = {
        "function_codes": ["INDICATE_GAP"],
        "function_version": "1.0.0",
        "move_links": [
            {
                "section_code": "INTRO",
                "move_code": "INTRO_GAP",
                "relation": "REALIZES_MOVE",
            }
        ],
        "step_links": [
            {
                "section_code": "INTRO",
                "move_code": "INTRO_GAP",
                "step_code": "INTRO_INDICATE",
                "relation": "REALIZES_STEP",
            }
        ],
        "usage_profiles": [
            {
                "section_code": "INTRO",
                "genre_code": "RESEARCH_ARTICLE",
                "language_code": "en",
                "register_code": "REGISTER_FORMAL_ACADEMIC",
                "discipline_code": "SCI",
                "preferred_usage": "general",
            }
        ],
        "pragmatic_tags": [
            {
                "code": "STANCE_EPISTEMIC",
                "version": "1.0.0",
                "context_note": "Frames a cautious gap claim.",
            }
        ],
        "examples": [
            {
                "kind": "positive",
                "text": (
                    "The role of federated learning in intermittent networks remains underexplored."
                ),
                "explanation": "Names a bounded research context.",
                "origin_kind": "illustrative_synthetic",
            },
            {
                "kind": "negative",
                "text": "Everything about this topic is unexplored.",
                "explanation": "Overstates the gap without a bounded literature review.",
                "origin_kind": "illustrative_synthetic",
            },
        ],
        "caveats": [
            {
                "code": "GAP_REQUIRES_REVIEW",
                "severity": "warning",
                "message": "Support a gap claim with a documented literature review.",
            }
        ],
    }
    created = await api_client.post(
        f"/v1/admin/academic-phrases/versions/{version.id}/metadata",
        headers={"X-API-Key": curator_key},
        json=payload,
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["communicative_functions"][0]["code"] == "INDICATE_GAP"
    assert created_body["communicative_functions"][0]["version"] == "1.0.0"
    assert created_body["move_links"][0]["code"] == "INTRO_GAP"
    assert created_body["step_links"][0]["code"] == "INTRO_INDICATE"
    assert created_body["usage_profiles"][0]["section_code"] == "INTRO"
    assert {item["kind"] for item in created_body["examples"]} == {"positive", "negative"}
    assert created_body["caveats"][0]["code"] == "GAP_REQUIRES_REVIEW"

    query = {
        "q": "underexplored",
        "function": "INDICATE_GAP",
        "function_version": "1.0.0",
        "section": "INTRO",
        "move": "INTRO_GAP",
        "step": "INTRO_INDICATE",
        "genre": "RESEARCH_ARTICLE",
        "register": "REGISTER_FORMAL_ACADEMIC",
        "register_version": "1.0.0",
        "domain": "SCI",
        "stance": "STANCE_EPISTEMIC",
        "stance_version": "1.0.0",
    }
    results = await api_client.get(
        "/v1/academic-phrases", params=query, headers={"X-API-Key": client_key}
    )
    assert results.status_code == 200, results.text
    body = results.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(version.pattern_id)
    assert body["items"][0]["pragmatic_tags"][0]["facet"] == "stance_type"
    assert body["items"][0]["pragmatic_tags"][0]["version"] == "1.0.0"

    intent_code = body["items"][0]["intent_code"]
    for code, expected in ((intent_code, 1), ("NO_SUCH_INTENT", 0)):
        by_intent = await api_client.get(
            "/v1/academic-phrases",
            params={"function": "INDICATE_GAP", "intent": code},
            headers={"X-API-Key": client_key},
        )
        assert by_intent.status_code == 200, by_intent.text
        assert by_intent.json()["total"] == expected

    second_write = await api_client.post(
        f"/v1/admin/academic-phrases/versions/{version.id}/metadata",
        headers={"X-API-Key": curator_key},
        json=payload,
    )
    assert second_write.status_code == 409


@pytest.mark.asyncio
async def test_apb_rejects_unresolved_codes_and_unlicensed_examples(api_client, session_factory):
    await _seed(session_factory)
    _, curator_key = await _create_key(session_factory, "curator")
    version = await _pattern_version(session_factory, "An unresolved issue concerns {topic}.")

    unresolved = await api_client.post(
        f"/v1/admin/academic-phrases/versions/{version.id}/metadata",
        headers={"X-API-Key": curator_key},
        json={
            "function_codes": ["INDICATE_GAP"],
            "usage_profiles": [{"section_code": "MOCK_SECTION"}],
        },
    )
    assert unresolved.status_code == 422
    assert "Unknown section code" in unresolved.text

    unlicensed = await api_client.post(
        f"/v1/admin/academic-phrases/versions/{version.id}/metadata",
        headers={"X-API-Key": curator_key},
        json={
            "function_codes": ["INDICATE_GAP"],
            "examples": [
                {
                    "kind": "positive",
                    "text": "Borrowed example.",
                    "origin_kind": "licensed",
                    "source_ref": "https://example.test/source",
                    "license_code": "PROPRIETARY",
                }
            ],
        },
    )
    assert unlicensed.status_code == 422
    assert "license that permits display" in unlicensed.text


@pytest.mark.asyncio
async def test_apb_metadata_write_requires_curator_role(api_client, session_factory):
    await _seed(session_factory)
    _, client_key = await _create_key(session_factory, "client")
    version = await _pattern_version(
        session_factory, "The role of {topic} in {context} remains underexplored."
    )

    response = await api_client.post(
        f"/v1/admin/academic-phrases/versions/{version.id}/metadata",
        headers={"X-API-Key": client_key},
        json={"function_codes": ["INDICATE_GAP"]},
    )

    assert response.status_code == 403
