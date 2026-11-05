"""Real loopback HTTP faults and a killed subprocess worker on an isolated DB schema."""

import asyncio
import os
import runpy
import subprocess
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from aprkb.core.config import settings
from aprkb.modules.corpus.blobstore import LocalBlobStore
from aprkb.modules.mining.models import Job, JobAttempt
from aprkb.worker.runner import run_once


def source(*, status=200, fail_first=None, delay=0):
    root = Path(__file__).resolve().parents[5]
    make = runpy.run_path(str(root / "scripts/manual/job_source.py"))["make_server"]
    server = make(port=0, status=status, fail_first=fail_first, delay=delay, retry_after=1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


async def enqueue(factory):
    async with factory() as session:
        job = Job(type="import_articles", payload={"source": "slr", "limit": 1})
        session.add(job)
        await session.commit()
        return job.id


def configure(monkeypatch, server):
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "slr_api_key", SecretStr("loopback-only"))
    monkeypatch.setattr(settings, "slr_api_base_url", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setattr(settings, "job_retry_base_seconds", 0.05)
    monkeypatch.setattr(settings, "job_retry_cap_seconds", 0.1)


@pytest.mark.parametrize("status,fail_first,expected", [(429, 2, 3), (503, 1, 2), (403, None, 1)])
async def test_real_http_failures_and_retry_after(
    postgres_test_engine,
    monkeypatch,
    tmp_path,
    status,
    fail_first,
    expected,
):
    server, thread = source(status=status, fail_first=fail_first)
    configure(monkeypatch, server)
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    job_id = await enqueue(factory)
    try:
        for index in range(expected):
            assert await run_once(factory, blob_store=LocalBlobStore(tmp_path))
            async with factory() as session:
                job = await session.get(Job, job_id)
                assert job.attempts == index + 1
                if index < expected - 1:
                    assert job.status == "queued" and job.error_code == f"http_{status}"
                    assert job.next_attempt_at > datetime.now(UTC)
                    # The real clock, not a forced due timestamp: an early poll must not claim.
                    scheduled = job.next_attempt_at
            if index < expected - 1:
                assert not await run_once(factory, blob_store=LocalBlobStore(tmp_path))
                await asyncio.sleep(max(0, (scheduled - datetime.now(UTC)).total_seconds()) + 0.05)
        async with factory() as session:
            job = await session.get(Job, job_id)
            assert job.status == ("failed" if status == 403 else "succeeded")
            rows = list(
                await session.scalars(
                    select(JobAttempt)
                    .where(JobAttempt.job_id == job_id)
                    .order_by(JobAttempt.attempt_no)
                )
            )
            assert len(rows) == expected
            for previous, following in zip(rows, rows[1:], strict=False):
                assert following.started_at >= previous.next_attempt_at
            if status == 403:
                assert job.error_code == "permission_denied" and job.next_attempt_at is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


async def test_forcibly_killed_process_recovers_without_touching_existing_workers(
    postgres_test_engine,
    monkeypatch,
    tmp_path,
):
    server, thread = source(delay=3)
    configure(monkeypatch, server)
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    async with factory() as session:
        schema = await session.scalar(text("SELECT current_schema()"))
    assert schema.startswith("test_")
    job_id = await enqueue(factory)
    backend = Path(__file__).resolve().parents[3]
    environment = dict(os.environ)
    environment.update(
        {
            "DATABASE_URL": os.environ["TEST_DATABASE_URL"],
            "APP_ENV": "test",
            "PYTHONPATH": str(backend / "src"),
            "MANUAL_TEST_SCHEMA": schema,
            "SLR_API_KEY": "loopback-only",
            "SLR_API_BASE_URL": settings.slr_api_base_url,
            "BLOB_DIR": str(tmp_path),
            "JOB_HEARTBEAT_SECONDS": "1",
            "JOB_LEASE_SECONDS": "5",
            "JOB_TIMEOUT_SECONDS": "20",
            "ARTICLE_SOURCE": "slr",
        }
    )
    script = """
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from aprkb.modules import load_models
from aprkb.core.logging import configure_logging
from aprkb.worker.runner import run_once
async def main():
    configure_logging()
    load_models()
    engine=create_async_engine(os.environ['DATABASE_URL'], connect_args={
        'server_settings': {'search_path': os.environ['MANUAL_TEST_SCHEMA']+',public'}})
    try:
        await run_once(async_sessionmaker(engine,expire_on_commit=False))
    finally:
        await engine.dispose()
asyncio.run(main())
"""
    with (tmp_path / "killed-worker.log").open("w", encoding="utf-8") as log:
        child = subprocess.Popen(
            [sys.executable, "-u", "-c", script],
            cwd=backend,
            env=environment,
            stdout=log,
            stderr=log,
        )
        try:
            active = False
            for _ in range(200):
                async with factory() as session:
                    job = await session.get(Job, job_id)
                    active = job.status == "processing" and job.progress_stage == "listing_articles"
                if active or child.poll() is not None:
                    break
                await asyncio.sleep(0.05)
            assert active, "Disposable worker did not enter the expected stage"
            # Only this test-created subprocess is killed; never enumerate/kill user processes.
            child.kill()
            await asyncio.to_thread(child.wait, 10)
            async with factory() as session:
                job = await session.get(Job, job_id)
                assert job.status == "processing" and job.attempts == 1
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(locked_at=datetime.now(UTC) - timedelta(hours=1))
                )
                await session.commit()
            assert await run_once(factory, blob_store=LocalBlobStore(tmp_path))
            async with factory() as session:
                job = await session.get(Job, job_id)
                assert job.status == "succeeded" and job.attempts == 2
                rows = list(
                    await session.scalars(
                        select(JobAttempt)
                        .where(JobAttempt.job_id == job_id)
                        .order_by(JobAttempt.attempt_no)
                    )
                )
                assert [row.outcome for row in rows] == ["interrupted", "succeeded"]
                assert rows[0].error_code == "lease_expired"
        finally:
            if child.poll() is None:
                child.kill()
                await asyncio.to_thread(child.wait, 10)
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


async def test_two_worker_processes_with_heartbeat_and_slow_http(
    postgres_test_engine,
    monkeypatch,
    tmp_path,
):
    server, thread = source(delay=4)
    configure(monkeypatch, server)
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    async with factory() as session:
        schema = await session.scalar(text("SELECT current_schema()"))
    assert schema.startswith("test_")
    ids = [await enqueue(factory) for _ in range(3)]
    backend = Path(__file__).resolve().parents[3]
    environment = dict(os.environ)
    environment.update(
        {
            "DATABASE_URL": os.environ["TEST_DATABASE_URL"],
            "APP_ENV": "test",
            "PYTHONPATH": str(backend / "src"),
            "MANUAL_TEST_SCHEMA": schema,
            "SLR_API_KEY": "loopback-only",
            "SLR_API_BASE_URL": settings.slr_api_base_url,
            "BLOB_DIR": str(tmp_path),
            "JOB_HEARTBEAT_SECONDS": "0.5",
            "JOB_LEASE_SECONDS": "2",
            "JOB_TIMEOUT_SECONDS": "20",
            "ARTICLE_SOURCE": "slr",
        }
    )
    script = """
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from aprkb.modules import load_models
from aprkb.core.logging import configure_logging
from aprkb.worker.runner import run_once
async def main():
    configure_logging()
    load_models()
    engine=create_async_engine(os.environ['DATABASE_URL'], connect_args={
        'server_settings': {'search_path': os.environ['MANUAL_TEST_SCHEMA']+',public'}})
    try:
        factory=async_sessionmaker(engine,expire_on_commit=False)
        while await run_once(factory):
            pass
    finally:
        await engine.dispose()
asyncio.run(main())
"""
    children = []
    logs = []
    observed_heartbeats = {}
    try:
        for index in range(2):
            log = (tmp_path / f"worker-{index}.log").open("w", encoding="utf-8")
            logs.append(log)
            children.append(
                subprocess.Popen(
                    [sys.executable, "-u", "-c", script],
                    cwd=backend,
                    env=environment,
                    stdout=log,
                    stderr=log,
                )
            )
        initial = {}
        for _ in range(600):
            async with factory() as session:
                jobs = list(await session.scalars(select(Job).where(Job.id.in_(ids))))
            for job in jobs:
                if job.status == "processing" and job.locked_at is not None:
                    initial.setdefault(job.id, job.locked_at)
                    if job.locked_at > initial[job.id]:
                        observed_heartbeats[job.id] = True
            if all(child.poll() is not None for child in children):
                break
            await asyncio.sleep(0.05)
        assert all(child.poll() == 0 for child in children), "Worker exited with error or timed out"
        assert observed_heartbeats, "No live heartbeat renewal observed"
        async with factory() as session:
            jobs = list(await session.scalars(select(Job).where(Job.id.in_(ids))))
            assert all(job.status == "succeeded" and job.attempts == 1 for job in jobs)
            attempts = list(
                await session.scalars(select(JobAttempt).where(JobAttempt.job_id.in_(ids)))
            )
            assert len(attempts) == 3 and all(row.outcome == "succeeded" for row in attempts)
        # Prove both processes did useful work instead of merely starting.
        for log in logs:
            log.flush()
        assert all(
            "Job claimed" in (tmp_path / f"worker-{index}.log").read_text(encoding="utf-8")
            for index in range(2)
        )
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            await asyncio.to_thread(child.wait, 10)
        for log in logs:
            log.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
