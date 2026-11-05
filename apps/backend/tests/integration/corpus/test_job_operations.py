"""Operator APIs with real PostgreSQL history/progress and existing key permissions."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.config import settings
from aprkb.core.deps import get_db_session
from aprkb.modules.audit.models import AuditEvent
from aprkb.modules.corpus.blobstore import LocalBlobStore
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.mining.models import Job, JobAttempt
from aprkb.modules.mining.queue import claim_next
from aprkb.seeds.load import run_seed
from aprkb.worker import runner
from aprkb.worker.progress import LeaseLost, make_reporter, report_progress


@pytest_asyncio.fixture
async def ops(postgres_test_engine):
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    keys = {}
    async with factory() as session:
        await run_seed(session)
        for role in ("curator", "reviewer", "client", "admin"):
            _, key = await create_api_key(session, name=f"Jobs {role}", role=role)
            keys[role] = {"X-API-Key": key}
        await session.commit()
    app = create_app()

    async def db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = db
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield factory, client, keys


async def add_job(factory, *, job_type="import_articles", max_attempts=2, status="queued"):
    async with factory() as session:
        job = Job(
            type=job_type,
            payload={"private": "not exposed"},
            max_attempts=max_attempts,
            status=status,
        )
        session.add(job)
        await session.commit()
        return job.id


async def make_due(factory, job_id):
    async with factory() as session:
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(next_attempt_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()


async def test_history_alert_ack_manual_retry_and_resolution(ops, monkeypatch, tmp_path):
    factory, client, keys = ops
    monkeypatch.setattr(settings, "job_failure_alert_threshold", 2)
    job_id = await add_job(factory)
    url = f"/v1/admin/jobs/{job_id}"

    async def fail(session, job, store):
        await report_progress("fetching_content", 1, 5)
        session.add(Job(type="uncommitted_child", payload={}))
        await session.flush()
        raise ConnectionError("secret manuscript MUST NOT appear in errors")

    monkeypatch.setattr(runner, "handle_job", fail)
    store = LocalBlobStore(tmp_path)
    for _ in range(2):
        await make_due(factory, job_id)
        await runner.run_once(factory, blob_store=store)
    response = await client.get(url + "/attempts", headers=keys["curator"])
    assert response.status_code == 200
    history = response.json()
    assert [row["attempt_no"] for row in history] == [2, 1]
    assert all(row["outcome"] == "failed" and row["ended_at"] for row in history)
    assert all(row["stage"] == "fetching_content" and row["completed"] == 1 for row in history)
    assert "secret manuscript" not in response.text
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Job)) == 1

    alerts = (await client.get("/v1/admin/job-alerts", headers=keys["curator"])).json()
    assert len(alerts) == 1 and alerts[0]["failure_count"] == 2
    alert = alerts[0]
    ack_url = f"/v1/admin/job-alerts/{alert['id']}/acknowledge"
    ack_body = {"expected_last_failed_at": alert["last_failed_at"]}
    assert (await client.post(ack_url, json=ack_body, headers=keys["reviewer"])).status_code == 403
    assert (await client.post(ack_url, json=ack_body, headers=keys["curator"])).json()[
        "acknowledged_at"
    ]
    assert (await client.post(ack_url, json=ack_body, headers=keys["curator"])).status_code == 200

    body = {"expected_attempts": 2, "rationale": "Network configuration repaired"}
    assert (
        await client.post(
            url + "/retry", json={**body, "expected_attempts": 1}, headers=keys["curator"]
        )
    ).status_code == 409
    assert (
        await client.post(
            url + "/retry", json={**body, "rationale": " " * 20}, headers=keys["curator"]
        )
    ).status_code == 422
    # Concurrent operator clicks queue only one additional attempt and one audit.
    results = await asyncio.gather(
        *(client.post(url + "/retry", json=body, headers=keys["curator"]) for _ in range(2))
    )
    assert sorted(result.status_code for result in results) == [200, 409]
    queued = next(result.json() for result in results if result.status_code == 200)
    assert queued["attempts"] == 2 and queued["max_attempts"] == 3
    assert queued["manual_retries"] == 1
    await runner.run_once(factory, blob_store=store)
    reopened = (await client.get("/v1/admin/job-alerts", headers=keys["curator"])).json()[0]
    assert reopened["id"] == alert["id"] and reopened["failure_count"] == 3
    assert reopened["acknowledged_at"] is None
    assert (await client.post(ack_url, json=ack_body, headers=keys["curator"])).status_code == 409

    async def succeed(session, job, store):
        await report_progress("saving_import_page", 5, 5)
        return None

    monkeypatch.setattr(runner, "handle_job", succeed)
    assert (
        await client.post(
            url + "/retry", json={**body, "expected_attempts": 3}, headers=keys["admin"]
        )
    ).status_code == 200
    await runner.run_once(factory, blob_store=store)
    job = (await client.get(url, headers=keys["curator"])).json()
    assert job["status"] == "succeeded" and job["attempts"] == 4
    assert job["progress_stage"] == "completed" and job["manual_retries"] == 2
    assert (await client.get("/v1/admin/job-alerts", headers=keys["curator"])).json() == []
    resolved = (
        await client.get("/v1/admin/job-alerts?active_only=false", headers=keys["admin"])
    ).json()[0]
    assert not resolved["active"] and resolved["resolved_at"]
    final = (await client.get(url + "/attempts", headers=keys["curator"])).json()
    assert [row["outcome"] for row in final] == ["succeeded", "failed", "failed", "failed"]
    assert final[-2:] == history
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "job.retry.manual")
            )
            == 2
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "job.alert.acknowledge")
            )
            == 1
        )


async def test_job_permissions_filters_and_manual_limits(ops, monkeypatch):
    factory, client, keys = ops
    monkeypatch.setattr(settings, "job_manual_retry_limit", 1)
    failed = await add_job(factory, status="failed", max_attempts=1)
    gold = await add_job(factory, job_type="label_gold", status="failed")
    live = await add_job(factory, status="processing")
    body = {"expected_attempts": 0, "rationale": "Corrected the configuration"}
    for role in ("client", "reviewer"):
        assert (await client.get("/v1/admin/jobs", headers=keys[role])).status_code == 403
        assert (
            await client.get(f"/v1/admin/jobs/{failed}/attempts", headers=keys[role])
        ).status_code == 403
        assert (
            await client.post(f"/v1/admin/jobs/{failed}/retry", json=body, headers=keys[role])
        ).status_code == 403
    for job_id in (gold, live):
        assert (
            await client.post(f"/v1/admin/jobs/{job_id}/retry", json=body, headers=keys["curator"])
        ).status_code == 409
    url = f"/v1/admin/jobs/{failed}"
    assert (
        await client.post(url + "/retry", json=body, headers=keys["curator"])
    ).status_code == 200
    async with factory() as session:
        await session.execute(update(Job).where(Job.id == failed).values(status="failed"))
        await session.commit()
    assert (
        await client.post(url + "/retry", json=body, headers=keys["curator"])
    ).status_code == 409
    listed = await client.get(
        "/v1/admin/jobs?status=failed&job_type=label_gold&limit=1", headers=keys["curator"]
    )
    assert listed.status_code == 200 and listed.json()[0]["id"] == str(gold)
    assert "payload" not in listed.text and "lock_token" not in listed.text
    assert (
        await client.get("/v1/admin/jobs?limit=201", headers=keys["curator"])
    ).status_code == 422
    assert (
        await client.get(f"/v1/admin/jobs/{uuid4()}/attempts", headers=keys["curator"])
    ).status_code == 404


async def test_live_progress_survives_cancel_and_recovery(ops, monkeypatch, tmp_path):
    factory, client, keys = ops
    job_id = await add_job(factory)
    ready = asyncio.Event()

    async def slow(session, job, store):
        await report_progress("fetching_content", 2, 9)
        session.add(Job(type="uncommitted_child", payload={}))
        await session.flush()
        ready.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(runner, "handle_job", slow)
    task = asyncio.create_task(runner.run_once(factory, blob_store=LocalBlobStore(tmp_path)))
    await asyncio.wait_for(ready.wait(), 10)
    try:
        data = (await client.get(f"/v1/admin/jobs/{job_id}", headers=keys["curator"])).json()
        assert data["status"] == "processing" and data["progress_completed"] == 2
        assert data["progress_stage"] == "fetching_content" and data["progress_total"] == 9
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Job)) == 1
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(locked_at=datetime.now(UTC) - timedelta(hours=1))
        )
        await session.commit()

    async def succeed(*args):
        return None

    monkeypatch.setattr(runner, "handle_job", succeed)
    await runner.run_once(factory, blob_store=LocalBlobStore(tmp_path))
    history = (
        await client.get(f"/v1/admin/jobs/{job_id}/attempts", headers=keys["curator"])
    ).json()
    assert [row["outcome"] for row in history] == ["succeeded", "interrupted"]
    assert history[1]["stage"] == "fetching_content" and history[1]["completed"] == 2


async def test_stale_progress_does_not_change_current_attempt(ops):
    factory, _, _ = ops
    job_id = await add_job(factory)
    async with factory() as session:
        job = await claim_next(session)
        old_token = job.lock_token
        await session.commit()
    async with factory() as session:
        await session.execute(update(Job).where(Job.id == job_id).values(lock_token=uuid4()))
        await session.commit()
    report = make_reporter(factory, job_id, old_token, 1)
    with pytest.raises(LeaseLost):
        await report("fetching_content", 1, 3)
    async with factory() as session:
        attempt = await session.scalar(select(JobAttempt).where(JobAttempt.job_id == job_id))
        assert attempt.stage == "starting" and attempt.completed is None


async def test_operations_migration_refuses_dropping_attempt_history(ops, postgres_test_engine):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    factory, _, _ = ops
    await add_job(factory)
    async with factory() as session:
        await claim_next(session)
        await session.commit()
    async with postgres_test_engine.begin() as connection:
        schema = await connection.scalar(text("SELECT current_schema()"))

        def downgrade(sync):
            root = Path(__file__).resolve().parents[3]
            config = Config(str(root / "alembic.ini"))
            config.set_main_option("script_location", str(root / "migrations"))
            config.attributes["connection"] = sync
            config.attributes["version_table_schema"] = schema
            command.downgrade(config, "0012_job_retry")

        with pytest.raises(RuntimeError, match="forward fix"):
            async with connection.begin_nested():
                await connection.run_sync(downgrade)
        assert await connection.scalar(text("SELECT count(*) FROM job_attempts")) == 1
        assert (
            await connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0013_job_operations"
        )
