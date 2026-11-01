from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.config import settings
from aprkb.core.deps import get_db_session
from aprkb.modules.audit.models import AuditEvent
from aprkb.modules.corpus.models import ImportProfile
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.mining.models import Job
from aprkb.seeds.load import run_seed


@pytest_asyncio.fixture
async def profile_context(postgres_test_engine: AsyncEngine, tmp_path: Path, monkeypatch):
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    async with factory() as session:
        await run_seed(session)
        curator = await create_api_key(session, name="profile curator", role="curator")
        reviewer = await create_api_key(session, name="profile reviewer", role="reviewer")
        client_key = await create_api_key(session, name="profile client", role="client")
        await session.commit()
    monkeypatch.setattr(settings, "blob_dir", str(tmp_path))
    monkeypatch.setattr(settings, "article_source", "slr")
    app = create_app()

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client,
    ):
        yield client, factory, curator[1], reviewer[1], client_key[1]


@pytest.mark.asyncio
async def test_profile_crud_audit_snapshot_and_role_permissions(profile_context) -> None:
    client, factory, curator_key, reviewer_key, client_key = profile_context
    curator = {"X-API-Key": curator_key}
    created = await client.post(
        "/v1/admin/corpus/import-profiles",
        headers=curator,
        json={
            "name": "Open access",
            "filters": {"q": "climate", "hasFullText": True},
            "artifact_kinds": ["FULLTEXT_MARKDOWN", "SOURCE_PDF"],
            "batch_limit": 12,
        },
    )
    assert created.status_code == 201, created.text
    profile_id = created.json()["id"]
    assert (
        await client.post(
            "/v1/admin/corpus/import-profiles", headers=curator, json={"name": "Open access"}
        )
    ).status_code == 409

    forbidden = await client.get(
        "/v1/admin/corpus/import-profiles", headers={"X-API-Key": reviewer_key}
    )
    forbidden_client = await client.get(
        "/v1/admin/corpus/import-profiles", headers={"X-API-Key": client_key}
    )
    assert forbidden.status_code == forbidden_client.status_code == 403

    enqueue = await client.post(
        "/v1/admin/corpus/imports", headers=curator, json={"profile_id": profile_id}
    )
    assert enqueue.status_code == 202
    job_id = UUID(enqueue.json()["job_id"])
    async with factory() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        snapshot = dict(job.payload)
        assert snapshot["profile_id"] == profile_id
        assert snapshot["filters"]["q"] == "climate"
        assert snapshot["artifact_kinds"] == ["FULLTEXT_MARKDOWN", "SOURCE_PDF"]
        assert snapshot["limit"] == 12

    updated = await client.patch(
        f"/v1/admin/corpus/import-profiles/{profile_id}",
        headers=curator,
        json={"filters": {"q": "education"}, "batch_limit": 5},
    )
    assert updated.status_code == 200
    async with factory() as session:
        job = await session.get(Job, job_id)
        profile = await session.get(ImportProfile, UUID(profile_id))
        assert job is not None and job.payload == snapshot
        assert profile is not None and profile.filters["q"] == "education"
        events = list((await session.scalars(select(AuditEvent))).all())
        assert {event.action for event in events} >= {
            "corpus.import_profile.create",
            "corpus.import_profile.update",
            "corpus.import.enqueue",
        }
