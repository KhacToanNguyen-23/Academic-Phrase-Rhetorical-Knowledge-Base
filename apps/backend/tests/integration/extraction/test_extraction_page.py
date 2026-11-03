"""Extraction page: batches, scoped mining, source text, and one-reviewer phrase decisions."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.deps import get_db_session
from aprkb.modules.audit.models import AuditEvent
from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.extraction.models import ApprovedPhrase
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.mining.models import Candidate, Job
from aprkb.seeds.load import run_seed

SENTENCE = "Our data report that it works."
SAFE_SLOTS = {
    "X": {"type": "noun_phrase", "signals": []},
    "Y": {"type": "clause", "signals": []},
}


@dataclass
class Seeded:
    batch_id: UUID
    article_id: UUID
    candidate_id: UUID
    sentence_id: UUID


@pytest_asyncio.fixture
async def session_factory(postgres_test_engine: AsyncEngine) -> AsyncIterator[async_sessionmaker]:
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    async with factory() as session:
        await run_seed(session)
        await session.commit()
    yield factory


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
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client,
    ):
        yield client


async def _key(session_factory: async_sessionmaker, role: str) -> dict[str, str]:
    async with session_factory() as session:
        _, key = await create_api_key(session, name=f"extraction-{role}-{uuid4()}", role=role)
        await session.commit()
    return {"X-API-Key": key}


async def _seed(
    session_factory: async_sessionmaker,
    *,
    batch_id: UUID | None = None,
    license_code: str = "CC-BY",
    ingest_status: str = "ready",
    slots: dict | None = None,
) -> Seeded:
    batch_id = batch_id or uuid4()
    async with session_factory() as session:
        license_row = await session.scalar(select(License).where(License.code == license_code))
        assert license_row is not None
        article = Article(
            license_id=license_row.id,
            blob_key="extraction/test.md",
            title="Extraction test article",
            ingest_status=ingest_status,
            import_batch_id=batch_id,
        )
        session.add(article)
        await session.flush()
        section = ArticleSection(
            article_id=article.id, section_code="INTRO", heading="Introduction", order=1
        )
        session.add(section)
        await session.flush()
        sentence = Sentence(
            article_id=article.id,
            article_section_id=section.id,
            text=SENTENCE,
            char_start=100,
            char_end=100 + len(SENTENCE),
        )
        session.add(sentence)
        await session.flush()
        candidate = Candidate(
            canonical_frame="[X] report that [Y].",
            slots=SAFE_SLOTS if slots is None else slots,
            epistemic_strength="moderate",
            source_sentence_ids=[sentence.id],
            occurrences=[
                {
                    "sentence_id": str(sentence.id),
                    "sentence_start": 100,
                    "sentence_end": 100 + len(SENTENCE),
                    "slot_spans": {"X": [100, 108], "Y": [121, 129]},
                }
            ],
            status="pending",
        )
        session.add(candidate)
        await session.commit()
        return Seeded(batch_id, article.id, candidate.id, sentence.id)


@pytest.mark.asyncio
async def test_roles_gate_every_endpoint(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    seeded = await _seed(session_factory)
    client_headers = await _key(session_factory, "client")
    reviewer = await _key(session_factory, "reviewer")

    for path in (
        "/v1/admin/corpus/batches",
        "/v1/admin/corpus/articles",
        f"/v1/admin/corpus/articles/{seeded.article_id}/text",
        "/v1/admin/extraction/phrases",
    ):
        assert (await api_client.get(path, headers=client_headers)).status_code == 403, path
        assert (await api_client.get(path)).status_code in {401, 403}, path

    mine = {"batch_ids": [str(seeded.batch_id)]}
    assert (
        await api_client.post("/v1/admin/corpus/mine", headers=client_headers, json=mine)
    ).status_code == 403
    # Reviewers can read and decide but cannot start mining jobs.
    assert (
        await api_client.post("/v1/admin/corpus/mine", headers=reviewer, json=mine)
    ).status_code == 403
    decision = {"decision": "reject"}
    assert (
        await api_client.post(
            f"/v1/admin/extraction/phrases/{seeded.candidate_id}/decision",
            headers=client_headers,
            json=decision,
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_batches_and_articles_report_status_and_phrase_counts(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    seeded = await _seed(session_factory)
    headers = await _key(session_factory, "reviewer")

    batches = (await api_client.get("/v1/admin/corpus/batches", headers=headers)).json()
    batch = next(row for row in batches if row["batch_id"] == str(seeded.batch_id))
    assert batch["articles"] == 1 and batch["ready"] == 1 and batch["mined"] == 0
    assert batch["phrases"] == {"pending": 1, "accepted": 0, "rejected": 0}

    articles = (
        await api_client.get(
            "/v1/admin/corpus/articles", headers=headers, params={"batch_id": str(seeded.batch_id)}
        )
    ).json()
    assert len(articles) == 1
    assert articles[0]["id"] == str(seeded.article_id)
    assert articles[0]["mining_status"] == "not_started"
    assert articles[0]["journal"] is None
    assert articles[0]["phrases"]["pending"] == 1

    # A finished mining job is reflected on both the article and its batch.
    async with session_factory() as session:
        session.add(
            Job(
                type="mine_article",
                payload={"article_id": str(seeded.article_id)},
                status="succeeded",
            )
        )
        await session.commit()
    batches = (await api_client.get("/v1/admin/corpus/batches", headers=headers)).json()
    batch = next(row for row in batches if row["batch_id"] == str(seeded.batch_id))
    assert batch["mined"] == 1
    articles = (
        await api_client.get(
            "/v1/admin/corpus/articles", headers=headers, params={"batch_id": str(seeded.batch_id)}
        )
    ).json()
    assert articles[0]["mining_status"] == "succeeded"


@pytest.mark.asyncio
async def test_mine_scope_queues_ready_articles_once_and_skips_the_rest(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    ready = await _seed(session_factory)
    pending = await _seed(session_factory, batch_id=ready.batch_id, ingest_status="pending")
    headers = await _key(session_factory, "curator")
    body = {"batch_ids": [str(ready.batch_id)]}

    first = await api_client.post("/v1/admin/corpus/mine", headers=headers, json=body)
    assert first.status_code == 202, first.text
    assert first.json()["articles"] == 2
    assert first.json()["skipped_not_ready"] == 1
    assert len(first.json()["job_ids"]) == 1

    again = await api_client.post("/v1/admin/corpus/mine", headers=headers, json=body)
    assert again.json()["job_ids"] == first.json()["job_ids"]

    async with session_factory() as session:
        jobs = list(await session.scalars(select(Job).where(Job.type == "mine_article")))
        queued_for = {job.payload["article_id"] for job in jobs}
        assert str(ready.article_id) in queued_for
        assert str(pending.article_id) not in queued_for

    articles = (
        await api_client.get(
            "/v1/admin/corpus/articles", headers=headers, params={"batch_id": str(ready.batch_id)}
        )
    ).json()
    status_by_id = {row["id"]: row["mining_status"] for row in articles}
    assert status_by_id[str(ready.article_id)] == "queued"
    assert status_by_id[str(pending.article_id)] == "not_started"

    empty = await api_client.post("/v1/admin/corpus/mine", headers=headers, json={})
    assert empty.status_code == 422


@pytest.mark.asyncio
async def test_article_text_requires_mining_rights(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    allowed = await _seed(session_factory)
    closed = await _seed(session_factory, license_code="PROPRIETARY")
    headers = await _key(session_factory, "reviewer")

    response = await api_client.get(
        f"/v1/admin/corpus/articles/{allowed.article_id}/text", headers=headers
    )
    assert response.status_code == 200
    sections = response.json()["sections"]
    assert sections[0]["heading"] == "Introduction"
    assert sections[0]["sentences"][0]["text"] == SENTENCE

    denied = await api_client.get(
        f"/v1/admin/corpus/articles/{closed.article_id}/text", headers=headers
    )
    assert denied.status_code == 403
    missing = await api_client.get(f"/v1/admin/corpus/articles/{uuid4()}/text", headers=headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_phrase_listing_returns_sources_with_sentence_relative_slot_spans(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    seeded = await _seed(session_factory)
    other = await _seed(session_factory)
    headers = await _key(session_factory, "reviewer")

    page = (
        await api_client.get(
            "/v1/admin/extraction/phrases",
            headers=headers,
            params={"article_id": str(seeded.article_id)},
        )
    ).json()
    assert page["total"] == 1
    item = page["items"][0]
    assert item["id"] == str(seeded.candidate_id)
    assert item["blocked"] is False
    assert item["canonical_frame"] == "[X] report that [Y]."
    source = item["sources"][0]
    assert source["text"] == SENTENCE
    assert source["section"] == "INTRO"
    assert source["slot_spans"] == {"X": [0, 8], "Y": [21, 29]}
    assert SENTENCE[0:8] == "Our data" and SENTENCE[21:29] == "it works"

    by_batch = (
        await api_client.get(
            "/v1/admin/extraction/phrases",
            headers=headers,
            params={"batch_id": [str(seeded.batch_id), str(other.batch_id)]},
        )
    ).json()
    assert by_batch["total"] == 2

    invalid = await api_client.get(
        "/v1/admin/extraction/phrases", headers=headers, params={"status": "bogus"}
    )
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_unlicensed_or_unsafe_phrases_are_blocked_and_cannot_be_accepted(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    closed = await _seed(session_factory, license_code="PROPRIETARY")
    unsafe = await _seed(session_factory, slots={"finding": "source wording"})
    headers = await _key(session_factory, "reviewer")

    page = (
        await api_client.get(
            "/v1/admin/extraction/phrases",
            headers=headers,
            params={"article_id": [str(closed.article_id), str(unsafe.article_id)]},
        )
    ).json()
    by_id = {item["id"]: item for item in page["items"]}
    assert by_id[str(closed.candidate_id)]["blocked"] is True
    assert by_id[str(closed.candidate_id)]["sources"] == []  # no text of an unlicensed article
    assert by_id[str(unsafe.candidate_id)]["blocked"] is True

    for seeded in (closed, unsafe):
        response = await api_client.post(
            f"/v1/admin/extraction/phrases/{seeded.candidate_id}/decision",
            headers=headers,
            json={"decision": "accept"},
        )
        assert response.status_code == 409, response.text
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ApprovedPhrase)) == 0
        candidate = await session.get(Candidate, closed.candidate_id)
        assert candidate is not None and candidate.status == "pending"

    # Rejecting stays possible so reviewers can clear the queue.
    reject = await api_client.post(
        f"/v1/admin/extraction/phrases/{closed.candidate_id}/decision",
        headers=headers,
        json={"decision": "reject"},
    )
    assert reject.status_code == 200 and reject.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_accept_stores_an_approved_phrase_once_and_audits_without_text(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    seeded = await _seed(session_factory)
    headers = await _key(session_factory, "reviewer")
    url = f"/v1/admin/extraction/phrases/{seeded.candidate_id}/decision"

    accepted = await api_client.post(
        url, headers=headers, json={"decision": "accept", "comment": "good journal phrase"}
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "accepted" and body["approved_phrase_id"]

    async with session_factory() as session:
        approved = await session.scalar(
            select(ApprovedPhrase).where(ApprovedPhrase.candidate_id == seeded.candidate_id)
        )
        assert approved is not None
        assert approved.canonical_frame == "[X] report that [Y]."
        assert approved.article_id == seeded.article_id
        assert approved.journal_id is None
        assert approved.source_sentence_ids == [seeded.sentence_id]
        assert approved.comment == "good journal phrase"
        candidate = await session.get(Candidate, seeded.candidate_id)
        assert candidate is not None and candidate.status == "accepted"
        # Not a pattern: accepting here never creates or links a PhrasePattern.
        assert candidate.matched_pattern_id is None
        audit = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "extraction.phrase.accept")
        )
        assert audit is not None
        assert audit.after["approved_phrase_id"] == body["approved_phrase_id"]
        assert SENTENCE not in str(audit.before) + str(audit.after)

    again = await api_client.post(url, headers=headers, json={"decision": "reject"})
    assert again.status_code == 409
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ApprovedPhrase)) == 1

    listed = (
        await api_client.get(
            "/v1/admin/extraction/phrases", headers=headers, params={"status": "accepted"}
        )
    ).json()
    assert str(seeded.candidate_id) in {item["id"] for item in listed["items"]}


@pytest.mark.asyncio
async def test_reject_never_creates_an_approved_phrase(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    seeded = await _seed(session_factory)
    headers = await _key(session_factory, "reviewer")

    response = await api_client.post(
        f"/v1/admin/extraction/phrases/{seeded.candidate_id}/decision",
        headers=headers,
        json={"decision": "reject"},
    )
    assert response.status_code == 200 and response.json()["approved_phrase_id"] is None
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ApprovedPhrase)) == 0
        candidate = await session.get(Candidate, seeded.candidate_id)
        assert candidate is not None and candidate.status == "rejected"

    missing = await api_client.post(
        f"/v1/admin/extraction/phrases/{uuid4()}/decision",
        headers=headers,
        json={"decision": "reject"},
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_bulk_decision_keeps_good_phrases_when_one_is_unsafe(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    good_a = await _seed(session_factory)
    good_b = await _seed(session_factory)
    bad = await _seed(session_factory, license_code="PROPRIETARY")
    headers = await _key(session_factory, "reviewer")

    response = await api_client.post(
        "/v1/admin/extraction/phrases/decisions",
        headers=headers,
        json={
            "candidate_ids": [
                str(good_a.candidate_id),
                str(bad.candidate_id),
                str(good_b.candidate_id),
                str(good_a.candidate_id),  # duplicates are processed once
            ],
            "decision": "accept",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert {row["candidate_id"] for row in body["results"]} == {
        str(good_a.candidate_id),
        str(good_b.candidate_id),
    }
    assert [row["candidate_id"] for row in body["failed"]] == [str(bad.candidate_id)]

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ApprovedPhrase)) == 2
        bad_candidate = await session.get(Candidate, bad.candidate_id)
        assert bad_candidate is not None and bad_candidate.status == "pending"
