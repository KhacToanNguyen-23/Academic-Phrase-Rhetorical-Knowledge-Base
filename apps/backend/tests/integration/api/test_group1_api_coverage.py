"""PostgreSQL API acceptance of Group 1, including negative request boundaries."""

import hashlib
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from aprkb.modules.identity.service import create_api_key
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    UsageConstraint,
)
from aprkb.modules.recommendation.models import RecommendationLog
from aprkb.modules.taxonomy.models import Intent, Move, Step
from aprkb.seeds.load import run_seed
from tests.integration.api.test_routes import api_client as api_client
from tests.integration.api.test_routes import session_factory as session_factory


@pytest_asyncio.fixture
async def group1_bank(session_factory):
    async with session_factory() as session:
        await run_seed(session)
        intent = await session.scalar(select(Intent).where(Intent.code == "INTRO_GAP_INDICATE"))
        move = await session.scalar(
            select(Move).join(Step, Step.move_id == Move.id).where(Step.id == intent.step_id)
        )
        fixtures = [
            ("The sentinel results suggest {finding}.", "approved", {"finding": "noun_phrase"}),
            (
                "The sentinel results suggest {conclusion}.",
                "approved",
                {"conclusion": "noun_phrase"},
            ),
            (
                "The sentinel results suggest {observation}.",
                "approved",
                {"observation": "noun_phrase"},
            ),
            ("A sentinel analysis uses {method}.", "approved", {"method": "noun_phrase"}),
            (
                "In this sentinel study, {topic} remains uncertain.",
                "approved",
                {"topic": "noun_phrase"},
            ),
            ("A sentinel draft must never be shown.", "draft", {}),
            ("A sentinel retired frame must never be shown.", "retired", {}),
        ]
        approved_ids = []
        for frame, status, slots in fixtures:
            pattern = PhrasePattern(intent_id=intent.id, status=status)
            session.add(pattern)
            await session.flush()
            version = PatternVersion(
                pattern_id=pattern.id,
                version_no=1,
                canonical_frame=frame,
                slots=slots,
                epistemic_strength="low",
                claim_type="descriptive",
            )
            session.add(version)
            await session.flush()
            pattern.current_version_id = version.id
            session.add_all(
                [
                    UsageConstraint(
                        pattern_version_id=version.id,
                        allowed_sections=["INTRO"],
                        allowed_genres=["RESEARCH_ARTICLE"],
                    ),
                    EvidenceProvenance(
                        pattern_version_id=version.id, source_type="authored", sentence_ids=[]
                    ),
                ]
            )
            if status == "approved":
                approved_ids.append(str(version.id))
        _, key = await create_api_key(session, name="group1-coverage", role="client")
        await session.commit()
        return {
            "headers": {"X-API-Key": key},
            "move": move.code,
            "intent": intent.code,
            "approved_ids": approved_ids,
        }


async def recommend(client, bank, **payload):
    response = await client.post(
        "/v1/recommendations",
        headers=bank["headers"],
        json={"move": bank["move"], "query": "sentinel", "limit": 3, **payload},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_APRKB_G1_TC_037_api_gates_mmr_trace_and_explanations(api_client, group1_bank):
    body = await recommend(api_client, group1_bank)
    assert len(body["items"]) == 3
    assert sum(tier["accepted_count"] for tier in body["fallback_trace"]) == 5
    # Current dev filters non-approved rows in SQL, before pipeline gate counters.
    assert body["excluded"].get("GATE_APPROVAL", 0) == 0
    assert sum("results suggest" in item["canonical_frame"] for item in body["items"]) == 1
    for item in body["items"]:
        assert item["pattern_version_id"] in group1_bank["approved_ids"]
        assert item["breakdown"]["intent"] == 0.7
        assert "Intent: 0.700" in item["explanations"]
        assert sum(
            detail["weight"] for detail in item["explanation_details"] if detail["available"]
        ) == pytest.approx(1)
        assert sum(
            (detail["value"] or 0) * detail["weight"] for detail in item["explanation_details"]
        ) == pytest.approx(item["score"])
    assert body["policy_versions"]["ranking_weights"] == "0.3.0"
    assert body["policy_versions"]["diversity"] == "0.1.0"


@pytest.mark.asyncio
async def test_APRKB_G1_TC_038_api_repeated_request_is_deterministic(api_client, group1_bank):
    first = await recommend(api_client, group1_bank)
    second = await recommend(api_client, group1_bank)
    assert first["items"] == second["items"]
    assert first["fallback_trace"] == second["fallback_trace"]
    assert first["context_hash"] == second["context_hash"]
    assert first["recommendation_id"] != second["recommendation_id"]


@pytest.mark.asyncio
async def test_APRKB_G1_TC_039_unknown_or_conflicting_context_returns_empty(
    api_client, group1_bank
):
    valid_codes = {
        "move": group1_bank["move"],
        "intent": group1_bank["intent"],
        "section": "INTRO",
        "genre": "RESEARCH_ARTICLE",
        "claim_type": "descriptive",
        "evidence_level": "single_study",
    }
    for field, value in valid_codes.items():
        assert (await recommend(api_client, group1_bank, **{field: value}))["items"]
    for payload in (
        {"move": "UNKNOWN_MOVE"},
        {"intent": "UNKNOWN_INTENT"},
        {"section": "UNKNOWN_SECTION"},
        {"genre": "UNKNOWN_GENRE"},
        {"claim_type": "UNKNOWN_CLAIM"},
        {"evidence_level": "UNKNOWN_EVIDENCE"},
        {"move": "UNKNOWN_MOVE", "intent": group1_bank["intent"]},
    ):
        body = await recommend(api_client, group1_bank, **payload)
        assert body["items"] == []
        assert all(tier["accepted_count"] == 0 for tier in body["fallback_trace"])
        assert body["recommendation_id"]
    for discipline in ("computer_science", "UNKNOWN_DISCIPLINE"):
        body = await recommend(api_client, group1_bank, discipline=discipline)
        assert body["items"]
        assert all(item["breakdown"]["discipline"] is None for item in body["items"])
        assert "Discipline affinity is unavailable and was not used for ranking" in body["warnings"]


@pytest.mark.asyncio
async def test_APRKB_G1_TC_040_http_field_boundaries(api_client, group1_bank):
    cases = [({"limit": 0}, "limit"), ({"limit": 101}, "limit"), ({"limit": "bad"}, "limit")]
    for payload, field in cases:
        response = await api_client.post(
            "/v1/recommendations",
            headers=group1_bank["headers"],
            json=payload,
        )
        assert response.status_code == 422, (field, response.text)
        errors = response.json()["error"]["details"]["errors"]
        assert any(field in error["loc"] for error in errors)
        assert response.headers["X-Request-ID"]
    first = await recommend(api_client, group1_bank, limit=1)
    all_items = await recommend(api_client, group1_bank, limit=100)
    assert len(first["items"]) == 1
    assert len(all_items["items"]) == 3
    assert first["items"][0] == all_items["items"][0]


@pytest.mark.asyncio
async def test_APRKB_G1_TC_041_literal_query_privacy_and_whitespace(
    api_client, group1_bank, session_factory
):
    ordinary = await recommend(api_client, group1_bank)
    padded = await recommend(api_client, group1_bank, query="  sentinel  ")
    assert ordinary["items"] == padded["items"]
    assert ordinary["context_hash"] == padded["context_hash"]
    async with session_factory() as session:
        log = await session.get(RecommendationLog, UUID(padded["recommendation_id"]))
        assert "query" not in log.request
        assert log.request["query_hash"] == hashlib.sha256(b"sentinel").hexdigest()
        before = await session.scalar(select(func.count()).select_from(PhrasePattern))
    for query in ("%_\\", "!?😀", "' ; DROP TABLE phrase_patterns; --", "Kết quả 😀"):
        body = await recommend(api_client, group1_bank, query=query)
        assert all("must never be shown" not in item["canonical_frame"] for item in body["items"])
        if query in ("%_\\", "!?😀"):
            assert body["items"] == []
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PhrasePattern)) == before


@pytest.mark.asyncio
async def test_APRKB_G1_TC_042_recommendation_requires_authentication(api_client, group1_bank):
    for headers in ({}, {"X-API-Key": "aprkb_invalid_fixture"}):
        response = await api_client.post("/v1/recommendations", headers=headers, json={})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
        assert "items" not in response.json()


@pytest.mark.asyncio
async def test_APRKB_G1_TC_043_render_is_bound_to_issued_client_and_version(
    api_client, group1_bank, session_factory
):
    body = await recommend(api_client, group1_bank)
    selected = body["items"][0]
    version_response = await api_client.get(
        f"/v1/patterns/versions/{selected['pattern_version_id']}", headers=group1_bank["headers"]
    )
    assert version_response.status_code == 200
    slots = {name: "test concept" for name in version_response.json()["slots"]}
    payload = {
        "recommendation_id": body["recommendation_id"],
        "pattern_version_id": selected["pattern_version_id"],
        "slots": slots,
    }
    valid = await api_client.post("/v1/render", headers=group1_bank["headers"], json=payload)
    assert valid.status_code == 200
    assert valid.json()["unfilled_slots"] == []
    issued = {item["pattern_version_id"] for item in body["items"]}
    unissued = next(version for version in group1_bank["approved_ids"] if version not in issued)
    for override in ({"recommendation_id": str(uuid4())}, {"pattern_version_id": unissued}):
        response = await api_client.post(
            "/v1/render",
            headers=group1_bank["headers"],
            json={**payload, **override},
        )
        assert response.status_code == 404
    async with session_factory() as session:
        _, other_key = await create_api_key(session, name="other-group1-client", role="client")
        await session.commit()
    response = await api_client.post(
        "/v1/render",
        headers={"X-API-Key": other_key},
        json=payload,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_APRKB_G1_TC_044_http_query_length_validation(api_client, group1_bank):
    for query in (None, "", "x" * 500):
        body = await recommend(api_client, group1_bank, query=query)
        assert "items" in body
    response = await api_client.post(
        "/v1/recommendations",
        headers=group1_bank["headers"],
        json={"query": "x" * 501},
    )
    assert response.status_code == 422
    assert any("query" in error["loc"] for error in response.json()["error"]["details"]["errors"])


@pytest.mark.asyncio
async def test_APRKB_G1_TC_045_http_journal_id_validation(api_client, group1_bank):
    response = await api_client.post(
        "/v1/recommendations",
        headers=group1_bank["headers"],
        json={"journal_id": "not-a-uuid"},
    )
    assert response.status_code == 422
    response = await api_client.post(
        "/v1/recommendations",
        headers=group1_bank["headers"],
        json={"journal_id": str(uuid4())},
    )
    assert response.status_code == 404
