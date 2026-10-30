from pathlib import Path
from shutil import copytree
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.deps import get_db_session
from aprkb.modules.audit.models import AuditEvent
from aprkb.modules.identity.service import authenticate_api_key, bootstrap_admin


@pytest.fixture
def session_factory(postgres_test_engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(postgres_test_engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_admin_api_key_create_list_revoke_only_returns_plaintext_on_create(
    session_factory: async_sessionmaker,
) -> None:
    async with session_factory() as session:
        current_schema = await session.scalar(text("SELECT current_schema()"))
        assert current_schema is not None and current_schema.startswith("test_")
        admin_client, admin_key = await bootstrap_admin(session, name="api key route admin")
        await session.commit()

    app = create_app()

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-API-Key": admin_key},
        ) as client,
    ):
        created = await client.post(
            "/v1/admin/api-keys",
            json={"name": "test client", "role": "client"},
        )
        assert created.status_code in {200, 201}
        assert created.headers.get("X-Request-ID")
        payload = created.json()
        plaintext_key = payload["api_key"]
        client_id = payload["id"]
        assert plaintext_key and plaintext_key != admin_key

        listed = await client.get("/v1/admin/api-keys")
        assert listed.status_code == 200
        assert listed.headers.get("X-Request-ID")
        assert plaintext_key not in listed.text
        assert "key_hash" not in listed.text

        last_admin_revoke = await client.delete(
            "/v1/admin/api-keys",
            params={"client_id": str(admin_client.id)},
        )
        assert last_admin_revoke.status_code == 409

        revoked = await client.delete(
            "/v1/admin/api-keys",
            params={"client_id": client_id},
        )
        assert revoked.status_code in {200, 204}
        assert revoked.headers.get("X-Request-ID")
        assert plaintext_key not in revoked.text

        async with session_factory() as session:
            assert await authenticate_api_key(session, plaintext_key) is None
            events = await session.scalars(
                select(AuditEvent).where(AuditEvent.entity_id == UUID(client_id))
            )
            key_events = list(events)
            assert {event.action for event in key_events} == {"api_key.create", "api_key.revoke"}
            assert plaintext_key not in repr([event.after for event in key_events])


@pytest.mark.asyncio
async def test_api_errors_use_standard_envelope_and_request_id_header(
    session_factory: async_sessionmaker,
) -> None:
    app = create_app()
    async with session_factory() as session:
        inactive_client, inactive_key = await bootstrap_admin(
            session, name="inactive route test admin"
        )
        inactive_client.is_active = False
        await session.commit()

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/v1/admin/api-keys")
        invalid_response = await client.get(
            "/v1/admin/api-keys", headers={"X-API-Key": "invalid-test-key"}
        )
        inactive_response = await client.get(
            "/v1/admin/api-keys", headers={"X-API-Key": inactive_key}
        )

    assert response.status_code == 401
    assert invalid_response.status_code == 401
    assert inactive_response.status_code == 401
    body = response.json()
    assert set(body) == {"error", "request_id"}
    assert set(body["error"]) == {"code", "message", "details"}
    request_id = response.headers.get("X-Request-ID")
    assert request_id
    assert body["request_id"] == request_id
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0


@pytest.mark.asyncio
async def test_invalid_policy_prevents_application_startup(tmp_path: Path) -> None:
    policy_source = Path(__file__).parents[3] / "src" / "aprkb" / "policies"
    policy_dir = tmp_path / "policies"
    copytree(policy_source, policy_dir)
    (policy_dir / "ranking_weights.yaml").write_text(
        "version: 0.1.0\nweights: []\n", encoding="utf-8"
    )
    app = create_app(policy_dir=policy_dir)

    with pytest.raises(ValueError):
        async with app.router.lifespan_context(app):
            pass
