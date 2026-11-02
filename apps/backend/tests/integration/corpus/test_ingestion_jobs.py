"""Phase 05 upload-to-candidate tests, authored before implementation."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.config import settings as core_settings
from aprkb.core.deps import get_db_session
from aprkb.modules.corpus import router as corpus_router
from aprkb.modules.corpus.models import Article, Sentence
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.mining.models import Candidate, Job
from aprkb.modules.mining.queue import claim_next
from aprkb.modules.patterns.models import PatternVersion, PhrasePattern
from aprkb.seeds.load import run_seed
from aprkb.worker.runner import run_once


@pytest_asyncio.fixture
async def phase05_sessions(
    postgres_test_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker]:
    yield async_sessionmaker(postgres_test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def phase05_client(
    phase05_sessions: async_sessionmaker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[AsyncClient, str]]:
    monkeypatch.setattr(core_settings, "blob_dir", str(tmp_path))
    app = create_app()

    async def override_db_session():
        async with phase05_sessions() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client,
    ):
        async with phase05_sessions() as session:
            actor, key = await create_api_key(session, name="phase05 curator", role="curator")
            del actor
            await session.commit()
        yield client, key


@pytest.mark.asyncio
async def test_upload_txt_then_worker_ingest_and_mine_creates_only_sourced_candidate(
    phase05_client: tuple[AsyncClient, str], phase05_sessions: async_sessionmaker, tmp_path: Path
) -> None:
    async with phase05_sessions() as session:
        await run_seed(session)
        await session.commit()
    client, key = phase05_client
    headers = {"X-API-Key": key}
    source = (
        "The results demonstrate that the proposed method improves retrieval accuracy. "
        "These findings indicate that contextual evidence can guide robust academic writing."
    )
    response = await client.post(
        "/v1/admin/corpus/articles",
        headers=headers,
        data={"title": "Worker fixture", "license_code": "CC-BY"},
        files={"file": ("article.txt", source.encode(), "text/plain")},
    )

    assert response.status_code == 202
    article_id = UUID(response.json()["article_id"])
    ingest_job_id = UUID(response.json()["job_id"])
    async with phase05_sessions() as session:
        before_patterns = await session.scalar(select(func.count()).select_from(PhrasePattern))
        before_versions = await session.scalar(select(func.count()).select_from(PatternVersion))

    await run_once(phase05_sessions)
    mine = await client.post(f"/v1/admin/corpus/articles/{article_id}/mine", headers=headers)
    assert mine.status_code == 202
    await run_once(phase05_sessions)

    async with phase05_sessions() as session:
        candidates = list(await session.scalars(select(Candidate)))
        sentence_ids = set(await session.scalars(select(Sentence.id)))
        ingest_job = await session.get(Job, ingest_job_id)
        assert ingest_job is not None and ingest_job.status == "succeeded"
        assert candidates
        assert all(candidate.source_sentence_ids for candidate in candidates)
        assert all(set(candidate.source_sentence_ids) <= sentence_ids for candidate in candidates)
        assert (
            await session.scalar(select(func.count()).select_from(PhrasePattern)) == before_patterns
        )
        assert (
            await session.scalar(select(func.count()).select_from(PatternVersion))
            == before_versions
        )
    assert (tmp_path / f"articles/{article_id.hex}.txt").exists()


@pytest.mark.asyncio
async def test_upload_preserves_scholarly_sentence_boundaries_and_offsets(
    phase05_client: tuple[AsyncClient, str], phase05_sessions: async_sessionmaker
) -> None:
    async with phase05_sessions() as session:
        await run_seed(session)
        await session.commit()
    client, key = phase05_client
    expected = [
        "Dr. Smith used examples, e.g. neural models.",
        "See Fig. 2 for the measured results.",
        'Smith et al. (2020) wrote "These results agree."',
        "We studied the U.S. in 2020.",
    ]
    source = "  " + "\r\n".join(expected) + "  "
    response = await client.post(
        "/v1/admin/corpus/articles",
        headers={"X-API-Key": key},
        data={"title": "Scholarly sentence fixture", "license_code": "CC-BY"},
        files={"file": ("sentences.txt", source.encode(), "text/plain")},
    )
    assert response.status_code == 202
    article_id = UUID(response.json()["article_id"])
    job_id = UUID(response.json()["job_id"])
    await run_once(phase05_sessions)

    async with phase05_sessions() as session:
        job = await session.get(Job, job_id)
        assert job is not None and job.status == "succeeded"
        sentences = list(
            await session.scalars(
                select(Sentence)
                .where(Sentence.article_id == article_id)
                .order_by(Sentence.char_start)
            )
        )
        assert [sentence.text for sentence in sentences] == expected
        assert all(
            source[sentence.char_start : sentence.char_end] == sentence.text
            for sentence in sentences
        )


@pytest.mark.asyncio
async def test_mining_before_ingest_is_ready_returns_conflict(
    phase05_client: tuple[AsyncClient, str], phase05_sessions: async_sessionmaker
) -> None:
    async with phase05_sessions() as session:
        await run_seed(session)
        await session.commit()
    client, key = phase05_client
    response = await client.post(
        "/v1/admin/corpus/articles",
        headers={"X-API-Key": key},
        data={"title": "Pending", "license_code": "CC-BY"},
        files={"file": ("article.txt", b"A short pending upload.", "text/plain")},
    )
    article_id = response.json()["article_id"]

    mine = await client.post(
        f"/v1/admin/corpus/articles/{article_id}/mine", headers={"X-API-Key": key}
    )

    assert mine.status_code == 409


@pytest.mark.asyncio
async def test_upload_removes_blob_when_database_persistence_fails(
    phase05_client: tuple[AsyncClient, str],
    phase05_sessions: async_sessionmaker,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with phase05_sessions() as session:
        await run_seed(session)
        await session.commit()
    client, key = phase05_client

    async def fail_upload(**_kwargs: object) -> None:
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(corpus_router, "create_upload", fail_upload)
    response = await client.post(
        "/v1/admin/corpus/articles",
        headers={"X-API-Key": key},
        data={"title": "DB failure", "license_code": "CC-BY"},
        files={"file": ("article.txt", b"Temporary content.", "text/plain")},
    )

    assert response.status_code == 500
    assert list((tmp_path / "articles").glob("*.txt")) == []


@pytest.mark.asyncio
async def test_non_mining_license_is_recorded_as_rejected_without_sentences(
    phase05_client: tuple[AsyncClient, str], phase05_sessions: async_sessionmaker
) -> None:
    async with phase05_sessions() as session:
        await run_seed(session)
        await session.commit()
    client, key = phase05_client
    response = await client.post(
        "/v1/admin/corpus/articles",
        headers={"X-API-Key": key},
        data={"title": "Restricted article", "license_code": "PROPRIETARY"},
        files={"file": ("article.txt", b"This content must not be mined.", "text/plain")},
    )
    article_id = UUID(response.json()["article_id"])
    job_id = UUID(response.json()["job_id"])

    await run_once(phase05_sessions)

    async with phase05_sessions() as session:
        article = await session.get(Article, article_id)
        job = await session.get(Job, job_id)
        assert article is not None and article.ingest_status == "rejected"
        assert job is not None and job.status == "failed" and "license" in (job.error or "").lower()


@pytest.mark.asyncio
async def test_two_workers_do_not_claim_the_same_job(phase05_sessions: async_sessionmaker) -> None:
    async with phase05_sessions() as session:
        job = Job(type="unknown", payload={}, status="queued")
        session.add(job)
        await session.commit()
        job_id = job.id

    async def claim() -> UUID | None:
        async with phase05_sessions() as session:
            job = await claim_next(session)
            await session.commit()
            return job.id if job is not None else None

    results = await asyncio.gather(claim(), claim())
    assert results.count(job_id) == 1
    assert results.count(None) == 1


@pytest.mark.asyncio
async def test_stale_processing_job_is_recovered_with_attempt_count(
    phase05_sessions: async_sessionmaker,
) -> None:
    stale_time = datetime.now(UTC) - timedelta(minutes=10)
    async with phase05_sessions() as session:
        job = Job(type="unknown", payload={}, status="processing", attempts=1, locked_at=stale_time)
        session.add(job)
        await session.commit()
        job_id = job.id

    async with phase05_sessions() as session:
        recovered = await claim_next(session, stale_after_seconds=300)
        assert recovered is not None and recovered.id == job_id
        assert recovered.attempts == 2
        assert recovered.locked_at is not None and recovered.locked_at > stale_time
        await session.rollback()


@pytest.mark.asyncio
async def test_parser_failure_finishes_job_and_marks_article_failed(
    phase05_client: tuple[AsyncClient, str], phase05_sessions: async_sessionmaker
) -> None:
    async with phase05_sessions() as session:
        await run_seed(session)
        await session.commit()
    client, key = phase05_client
    response = await client.post(
        "/v1/admin/corpus/articles",
        headers={"X-API-Key": key},
        data={"title": "Invalid UTF-8", "license_code": "CC-BY"},
        files={"file": ("article.txt", b"\xff\xfe", "text/plain")},
    )
    article_id = UUID(response.json()["article_id"])
    job_id = UUID(response.json()["job_id"])

    await run_once(phase05_sessions)

    async with phase05_sessions() as session:
        article = await session.get(Article, article_id)
        job = await session.get(Job, job_id)
        assert article is not None and article.ingest_status == "failed"
        assert job is not None and job.status == "failed"
        assert job.error == "Processing failed (UnicodeDecodeError)"
