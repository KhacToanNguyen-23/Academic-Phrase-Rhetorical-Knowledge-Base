"""Offline promotion to Online reads, using only the isolated aprkb_test fixture."""

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.config import settings
from aprkb.core.deps import get_db_session
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.mining.models import Candidate
from aprkb.modules.taxonomy.models import Intent
from aprkb.seeds.load import run_seed
from aprkb.worker.runner import run_once
from tests.seed_data import seed_legacy_pattern_fixtures

ARTICLE = (
    "The invented results demonstrate that the proposed method improves retrieval accuracy. "
    "These invented findings indicate that contextual evidence can guide clear writing. "
    "Prior invented studies have shown that adaptive sampling reduces annotation cost. "
    "We argue that transparent provenance supports reliable phrase reuse."
)


@pytest_asyncio.fixture
async def read_contract_sessions(
    postgres_test_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker]:
    yield async_sessionmaker(postgres_test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def read_contract_client(
    read_contract_sessions: async_sessionmaker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    monkeypatch.setattr(settings, "blob_dir", str(tmp_path))
    monkeypatch.setattr(settings, "app_env", "test")
    app = create_app()

    async def override() -> AsyncIterator:
        async with read_contract_sessions() as session:
            yield session

    app.dependency_overrides[get_db_session] = override
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


@pytest.mark.asyncio
async def test_approved_mined_patterns_reach_online_reads_and_render(
    read_contract_client: AsyncClient, read_contract_sessions: async_sessionmaker
) -> None:
    async with read_contract_sessions() as session:
        await run_seed(session)
        await seed_legacy_pattern_fixtures(session)
        await session.commit()
        _, curator = await create_api_key(session, name="read curator", role="curator")
        _, reviewer_one = await create_api_key(session, name="read reviewer one", role="reviewer")
        _, reviewer_two = await create_api_key(session, name="read reviewer two", role="reviewer")
        _, client_key = await create_api_key(session, name="read client", role="client")
        await session.commit()

    def auth(key: str) -> dict[str, str]:
        return {"X-API-Key": key}

    uploaded = await read_contract_client.post(
        "/v1/admin/corpus/articles",
        headers=auth(curator),
        data={"title": "Invented article", "license_code": "CC-BY"},
        files={"file": ("invented.txt", ARTICLE.encode(), "text/plain")},
    )
    assert uploaded.status_code == 202, uploaded.text
    article_id = UUID(uploaded.json()["article_id"])
    await run_once(read_contract_sessions)
    mining = await read_contract_client.post(
        f"/v1/admin/corpus/articles/{article_id}/mine", headers=auth(curator)
    )
    assert mining.status_code in {200, 202}, mining.text
    await run_once(read_contract_sessions)

    async with read_contract_sessions() as session:
        candidates = list(await session.scalars(select(Candidate)))
        intent = (await session.scalars(select(Intent))).first()
        assert candidates and intent is not None

    label_payload = {
        "intent_id": str(intent.id),
    }
    labels_path = f"/v1/admin/review-queue/{candidates[0].id}/intent"
    forbidden = await read_contract_client.put(
        labels_path, headers=auth(client_key), json=label_payload
    )
    assert forbidden.status_code == 403
    invalid = await read_contract_client.put(
        labels_path,
        headers=auth(reviewer_one),
        json={**label_payload, "intent_id": str(uuid4())},
    )
    assert invalid.status_code == 422
    missing_intent = await read_contract_client.post(
        f"/v1/admin/review-queue/{candidates[0].id}/decisions",
        headers=auth(reviewer_one),
        json={"decision": "approve"},
    )
    assert missing_intent.status_code == 409

    promoted: set[str] = set()
    for candidate in candidates:
        labelled = await read_contract_client.put(
            f"/v1/admin/review-queue/{candidate.id}/intent",
            headers=auth(reviewer_one),
            json=label_payload,
        )
        assert labelled.status_code == 200, labelled.text
        assert labelled.json()["intent_id"] == str(intent.id)
        first = await read_contract_client.post(
            f"/v1/admin/review-queue/{candidate.id}/decisions",
            headers=auth(reviewer_one),
            json={"decision": "approve", "comment": "invented fixture"},
        )
        frozen = await read_contract_client.put(
            f"/v1/admin/review-queue/{candidate.id}/intent",
            headers=auth(reviewer_two),
            json=label_payload,
        )
        assert frozen.status_code == 409
        second = await read_contract_client.post(
            f"/v1/admin/review-queue/{candidate.id}/decisions",
            headers=auth(reviewer_two),
            json={"decision": "approve", "comment": "invented fixture"},
        )
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        if second.json().get("pattern_version_id"):
            promoted.add(second.json()["pattern_version_id"])
    assert promoted
    completed = await read_contract_client.put(
        labels_path,
        headers=auth(reviewer_one),
        json=label_payload,
    )
    assert completed.status_code == 409

    listed = await read_contract_client.get(
        "/v1/patterns", params={"status": "approved", "limit": 200}, headers=auth(client_key)
    )
    assert listed.status_code == 200, listed.text
    mined = [row for row in listed.json() if row["current_version_id"] in promoted]
    assert mined
    for row in mined:
        assert row["claim_type"] is None and row["claim_type_labelled"] is False
        assert row["source_type"] == "mined"
        assert row["license_code"] == "CC-BY"
        assert row["source_sentence_count"] > 0
        assert row["article_id"] == str(article_id)
        assert row["source_reference"] is None
        detail = await read_contract_client.get(
            f"/v1/patterns/{row['id']}", headers=auth(client_key)
        )
        version = await read_contract_client.get(
            f"/v1/patterns/versions/{row['current_version_id']}", headers=auth(client_key)
        )
        assert detail.status_code == version.status_code == 200
        assert detail.json()["variants"] == row["variants"]
        assert version.json()["source_sentence_count"] == row["source_sentence_count"]

    recommended = await read_contract_client.post(
        "/v1/recommendations", json={"limit": 100}, headers=auth(client_key)
    )
    assert recommended.status_code == 200, recommended.text
    recommended_items = {item["pattern_version_id"]: item for item in recommended.json()["items"]}
    assert promoted.intersection(recommended_items)
    bracket_pattern = next(
        (row for row in mined if "{" in row["canonical_frame"] and row["slots"]), None
    )
    assert bracket_pattern is not None
    rendered = await read_contract_client.post(
        "/v1/render",
        headers=auth(client_key),
        json={
            "recommendation_id": recommended.json()["recommendation_id"],
            "pattern_version_id": bracket_pattern["current_version_id"],
            "slots": {name: "invented example" for name in bracket_pattern["slots"]},
        },
    )
    assert rendered.status_code == 200, rendered.text
    assert "invented example" in rendered.json()["text"]
