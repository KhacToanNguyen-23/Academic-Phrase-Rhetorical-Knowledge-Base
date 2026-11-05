"""Real PostgreSQL lease, retry, crash rollback, and duplicate-worker regressions."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aprkb.core.config import settings
from aprkb.modules.corpus.blobstore import LocalBlobStore
from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.corpus.sources.base import SourceArticleRef, SourcePage
from aprkb.modules.mining.models import Candidate, Job
from aprkb.modules.mining.queue import claim_next
from aprkb.seeds.load import run_seed
from aprkb.worker import runner


@pytest.fixture
def sessions(postgres_test_engine):
    return async_sessionmaker(postgres_test_engine, expire_on_commit=False)


async def enqueue(sessions, **kwargs):
    async with sessions() as session:
        job = Job(type="ingest_article", payload={}, **kwargs)
        session.add(job)
        await session.commit()
        return job.id


async def due(sessions, job_id):
    async with sessions() as session:
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(next_attempt_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()


async def test_transient_failure_is_delayed_bounded_and_redacted(sessions, monkeypatch, tmp_path):
    calls = 0

    async def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise ConnectionError("DO NOT STORE manuscript or secret")

    monkeypatch.setattr(runner, "handle_job", fail)
    job_id = await enqueue(sessions, max_attempts=2)
    store = LocalBlobStore(tmp_path)
    assert await runner.run_once(sessions, blob_store=store)
    assert not await runner.run_once(sessions, blob_store=store)
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job.status == "queued" and job.attempts == 1
        assert job.next_attempt_at > datetime.now(UTC)
        assert job.error_code == "transport_unavailable"
        assert "secret" not in job.error
    await due(sessions, job_id)
    assert await runner.run_once(sessions, blob_store=store)
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job.status == "failed" and job.attempts == 2
        assert job.next_attempt_at is None and job.lock_token is None
    assert not await runner.run_once(sessions, blob_store=store)
    assert calls == 2


async def test_retry_after_is_not_shortened_by_backoff_cap(sessions, monkeypatch, tmp_path):
    async def limited(*args, **kwargs):
        response = httpx.Response(
            429,
            headers={"Retry-After": "900"},
            request=httpx.Request("GET", "https://example.invalid"),
        )
        response.raise_for_status()

    monkeypatch.setattr(runner, "handle_job", limited)
    job_id = await enqueue(sessions)
    before = datetime.now(UTC)
    await runner.run_once(sessions, blob_store=LocalBlobStore(tmp_path))
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job.next_attempt_at >= before + timedelta(seconds=900)
        assert job.error_code == "http_429"


@pytest.mark.parametrize("error", [PermissionError("secret"), ValueError("bad data")])
async def test_permanent_error_is_not_retried(sessions, monkeypatch, tmp_path, error):
    async def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(runner, "handle_job", fail)
    job_id = await enqueue(sessions)
    await runner.run_once(sessions, blob_store=LocalBlobStore(tmp_path))
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job.status == "failed" and job.attempts == 1
        assert job.next_attempt_at is None


async def test_stale_owner_cannot_heartbeat_or_overwrite_new_attempt(sessions):
    job_id = await enqueue(sessions)
    async with sessions() as session:
        first = await claim_next(session)
        old = first.lock_token
        await session.commit()
    async with sessions() as session:
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(locked_at=datetime.now(UTC) - timedelta(minutes=10))
        )
        await session.commit()
    async with sessions() as session:
        second = await claim_next(session)
        new = second.lock_token
        await session.commit()
    assert new != old
    assert not await runner.heartbeat(sessions, job_id, old)
    await runner.record_failure(sessions, job_id=job_id, token=old, error=ConnectionError())
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job.lock_token == new and job.status == "processing" and job.attempts == 2


async def test_stale_recovery_has_a_hard_attempt_limit(sessions):
    job_id = await enqueue(
        sessions,
        status="processing",
        attempts=4,
        max_attempts=4,
        locked_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    # A poll with no runnable work must still commit terminal exhausted states.
    assert not await runner.run_once(sessions)
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job.status == "failed" and job.error_code == "attempts_exhausted"


async def test_heartbeat_and_live_transaction_prevent_takeover(sessions, monkeypatch, tmp_path):
    started, finish = asyncio.Event(), asyncio.Event()
    monkeypatch.setattr(settings, "job_heartbeat_seconds", 0.02)
    monkeypatch.setattr(settings, "job_lease_seconds", 0.1)

    async def slow(*args, **kwargs):
        started.set()
        await finish.wait()
        return None

    monkeypatch.setattr(runner, "handle_job", slow)
    job_id = await enqueue(sessions)
    worker = asyncio.create_task(runner.run_once(sessions, blob_store=LocalBlobStore(tmp_path)))
    try:
        await asyncio.wait_for(started.wait(), 5)
        async with sessions() as session:
            initial = (await session.get(Job, job_id)).locked_at
        for _ in range(100):
            await asyncio.sleep(0.02)
            async with sessions() as session:
                latest = (await session.get(Job, job_id)).locked_at
            if latest > initial:
                break
        assert latest > initial
        # Even with an artificially expired clock, the live transaction lock wins.
        async with sessions() as session:
            assert await claim_next(session, now=datetime.now(UTC) + timedelta(hours=1)) is None
            await session.commit()
        assert not await runner.run_once(sessions, blob_store=LocalBlobStore(tmp_path))
    finally:
        finish.set()
        await asyncio.wait_for(worker, 5)
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job.status == "succeeded" and job.attempts == 1


async def test_cancelled_attempt_rolls_back_output_then_recovers(sessions, monkeypatch, tmp_path):
    started = asyncio.Event()
    original = runner.handle_job

    async def interrupted(session, job, store):
        store.put("attempts/uncommitted.txt", b"test")
        session.add(Job(type="child_must_rollback", payload={}))
        await session.flush()
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(runner, "handle_job", interrupted)
    job_id = await enqueue(sessions)
    store = LocalBlobStore(tmp_path)
    worker = asyncio.create_task(runner.run_once(sessions, blob_store=store))
    await asyncio.wait_for(started.wait(), 5)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
    assert not (tmp_path / "attempts/uncommitted.txt").exists()
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Job)) == 1
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(locked_at=datetime.now(UTC) - timedelta(minutes=10))
        )
        await session.commit()
    monkeypatch.setattr(runner, "handle_job", original)
    # Real handler rejects missing article_id permanently; it was only run once after recovery.
    await runner.run_once(sessions, blob_store=store)
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job.attempts == 2 and job.status == "failed"


async def test_repeated_ingest_and_mine_do_not_duplicate_data(sessions, tmp_path):
    store = LocalBlobStore(tmp_path)
    store.put(
        "articles/authored.md",
        b"# Results\n\nThe results demonstrate that the method improves accuracy.",
    )
    async with sessions() as session:
        await run_seed(session)
        license_id = await session.scalar(select(License.id).where(License.code == "CC-BY"))
        article = Article(
            blob_key="articles/authored.md", license_id=license_id, ingest_status="pending"
        )
        session.add(article)
        await session.flush()
        article_id = article.id
        session.add_all(
            [Job(type="ingest_article", payload={"article_id": str(article_id)}) for _ in range(2)]
        )
        await session.commit()
    await asyncio.gather(*(runner.run_once(sessions, blob_store=store) for _ in range(2)))
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ArticleSection)) == 1
        assert await session.scalar(select(func.count()).select_from(Sentence)) == 1
        session.add_all(
            [Job(type="mine_article", payload={"article_id": str(article_id)}) for _ in range(2)]
        )
        await session.commit()
    await asyncio.gather(*(runner.run_once(sessions, blob_store=store) for _ in range(2)))
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Candidate)) == 1
        assert (
            await session.scalar(
                select(func.count()).select_from(Job).where(Job.status == "succeeded")
            )
            == 4
        )


async def test_lost_token_rolls_back_candidate_output(sessions, monkeypatch, tmp_path):
    async def invalidated(session, job, store):
        session.add(Job(type="must_rollback", payload={}))
        # Simulate external revocation while output remains uncommitted.
        async with sessions() as other:
            await other.execute(update(Job).where(Job.id == job.id).values(lock_token=uuid4()))
            await other.commit()
        return None

    monkeypatch.setattr(runner, "handle_job", invalidated)
    job_id = await enqueue(sessions)
    await runner.run_once(sessions, blob_store=LocalBlobStore(tmp_path))
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Job)) == 1
        assert (await session.get(Job, job_id)).status == "processing"


class ImportSource:
    name = "retry-test"

    def __init__(self, *, fail_once=False):
        self.fail_once = fail_once

    async def list_articles(self, **kwargs):
        return SourcePage(
            tuple(
                SourceArticleRef(
                    external_id=name,
                    title=name,
                    doi=f"10.test/{name}",
                    license_code="CC-BY",
                    content_type="text/markdown",
                )
                for name in ("a", "b")
            ),
            "page-2",
        )

    async def fetch_content(self, article):
        if article.external_id == "b" and self.fail_once:
            self.fail_once = False
            raise ConnectionError("transient")
        await asyncio.sleep(0)
        # Distinct source papers need distinct bytes now that corpus imports
        # also deduplicate by content hash across source IDs and DOIs.
        return (
            b"# Results\n\nThe results demonstrate that accuracy improves."
            + f"\n\nPaper {article.external_id}.".encode()
        )


async def create_imports(sessions, count=1):
    async with sessions() as session:
        await run_seed(session)
        jobs = [
            Job(type="import_articles", payload={"source": "retry-test", "limit": 2})
            for _ in range(count)
        ]
        session.add_all(jobs)
        await session.commit()
        return [job.id for job in jobs]


async def test_partial_import_failure_rolls_back_then_retries_only_that_page(sessions, tmp_path):
    source = ImportSource(fail_once=True)
    (job_id,) = await create_imports(sessions)
    store = LocalBlobStore(tmp_path)
    await runner.run_once(sessions, blob_store=store, article_source_factory=lambda _: source)
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Article)) == 0
        assert await session.scalar(select(func.count()).select_from(Job)) == 1
    assert not list(tmp_path.rglob("*.md"))
    await due(sessions, job_id)
    await runner.run_once(sessions, blob_store=store, article_source_factory=lambda _: source)
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job.status == "succeeded" and job.attempts == 2
        assert job.result["imported"] == 2
        assert await session.scalar(select(func.count()).select_from(Article)) == 2
        # One successful page creates two ingest jobs and exactly one continuation.
        assert await session.scalar(select(func.count()).select_from(Job)) == 4
    assert len(list(tmp_path.rglob("*.md"))) == 2


async def test_concurrent_imports_share_corpus_lock_without_duplicate_articles(sessions, tmp_path):
    ids = await create_imports(sessions, count=2)
    source = ImportSource()
    store = LocalBlobStore(tmp_path)
    await asyncio.gather(
        *(
            runner.run_once(sessions, blob_store=store, article_source_factory=lambda _: source)
            for _ in range(2)
        )
    )
    async with sessions() as session:
        jobs = list(await session.scalars(select(Job).where(Job.id.in_(ids))))
        assert all(job.status == "succeeded" for job in jobs)
        assert sorted(job.result["imported"] for job in jobs) == [0, 2]
        assert await session.scalar(select(func.count()).select_from(Article)) == 2
        assert (
            await session.scalar(
                select(func.count()).select_from(Job).where(Job.type == "ingest_article")
            )
            == 2
        )
    assert len(list(tmp_path.rglob("*.md"))) == 2


async def test_attempt_timeout_rolls_back_and_schedules_retry(sessions, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "job_timeout_seconds", 0.05)

    async def hanging(session, job, store):
        session.add(Job(type="must_rollback", payload={}))
        await session.flush()
        await asyncio.Event().wait()

    monkeypatch.setattr(runner, "handle_job", hanging)
    job_id = await enqueue(sessions)
    await runner.run_once(sessions, blob_store=LocalBlobStore(tmp_path))
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job.status == "queued" and job.error_code == "transport_unavailable"
        assert job.next_attempt_at is not None
        assert await session.scalar(select(func.count()).select_from(Job)) == 1


async def test_lost_commit_ack_keeps_success_and_its_blobs(sessions, monkeypatch, tmp_path):
    original_commit = AsyncSession.commit

    async def commit_with_lost_ack(session):
        await original_commit(session)
        if session.info.get("lose_ack"):
            raise ConnectionError("commit acknowledgement lost")

    async def handler(session, job, store):
        store.put("articles/committed.md", b"committed")
        job.result = {"saved": True}
        session.info["lose_ack"] = True
        return None

    monkeypatch.setattr(AsyncSession, "commit", commit_with_lost_ack)
    monkeypatch.setattr(runner, "handle_job", handler)
    job_id = await enqueue(sessions)
    await runner.run_once(sessions, blob_store=LocalBlobStore(tmp_path))
    assert (tmp_path / "articles/committed.md").read_bytes() == b"committed"
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job.status == "succeeded" and job.result == {"saved": True}
        assert job.attempts == 1 and job.next_attempt_at is None
