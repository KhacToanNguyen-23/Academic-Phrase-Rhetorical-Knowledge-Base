"""PostgreSQL integration coverage for batch frame statistics."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aprkb.modules.corpus.models import Article, License, Sentence
from aprkb.modules.extraction.phrase_stats import PhraseStatsRequest, compute_phrase_stats
from aprkb.modules.extraction.phrase_stats_repository import candidate_articles
from aprkb.modules.mining.models import Candidate
from aprkb.policies.loader import load_policy_bundle


@pytest_asyncio.fixture
async def phrase_stats_session(postgres_test_engine) -> AsyncSession:
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


async def _article(session: AsyncSession, license_id: UUID, batch_id: UUID) -> tuple[UUID, UUID]:
    article_id, sentence_id = uuid4(), uuid4()
    text = "Self-authored sentence used only for aggregate statistics tests."
    session.add(
        Article(
            id=article_id,
            source="upload",
            external_id=None,
            doi=None,
            title="Self-authored phrase statistics fixture",
            license_id=license_id,
            blob_key=f"phrase-stats/{article_id}",
            ingest_status="ready",
            import_batch_id=batch_id,
        )
    )
    session.add(
        Sentence(
            id=sentence_id,
            article_id=article_id,
            text=text,
            char_start=0,
            char_end=len(text),
        )
    )
    await session.flush()
    return article_id, sentence_id


async def _candidate(
    session: AsyncSession,
    sentence_id: UUID,
    frame: str,
    *,
    status: str = "pending",
    slot_marker: str = "number",
) -> None:
    session.add(
        Candidate(
            canonical_frame=frame,
            source_sentence_ids=[sentence_id],
            slots={"X": {"type": "noun_phrase", "signals": [slot_marker]}},
            status=status,
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_phrase_stats_counts_documents_not_candidate_rows(phrase_stats_session) -> None:
    session = phrase_stats_session
    license_row = License(
        code=f"TEST-{uuid4().hex[:12]}",
        name="Self-authored integration-test license",
        allows_mining=True,
        allows_display=True,
    )
    session.add(license_row)
    await session.flush()
    focal_batch, background_batch = uuid4(), uuid4()
    focal_articles = [await _article(session, license_row.id, focal_batch) for _ in range(10)]
    background_articles = [
        await _article(session, license_row.id, background_batch) for _ in range(10)
    ]

    for _article_id, sentence_id in focal_articles:
        await _candidate(session, sentence_id, "[X] common frame.")
    for _article_id, sentence_id in background_articles:
        await _candidate(session, sentence_id, "[X] common frame.")
    repeated_sentence = focal_articles[0][1]
    signals = ("number", "acronym", "year")
    for index in range(10):
        await _candidate(
            session,
            repeated_sentence,
            "[X] focal frame.",
            slot_marker=signals[index % len(signals)],
        )
    await _candidate(session, focal_articles[1][1], "[X] focal frame.", slot_marker="other")
    await _candidate(
        session,
        background_articles[0][1],
        "[X] focal frame.",
        status="rejected",
    )
    await session.commit()

    result = compute_phrase_stats(
        await candidate_articles(session),
        PhraseStatsRequest(
            focal_batch_id=focal_batch,
            background_batch_ids=(background_batch,),
        ),
        load_policy_bundle().phrase_stats,
    )
    by_frame = {row.frame: row for row in result.score_ranking}

    assert result.n_focal == result.n_bg == 10
    assert by_frame["[X] focal frame."].df_focal == 2
    assert by_frame["[X] focal frame."].occurrences == 11
    assert by_frame["[X] common frame."].df_focal == 10
    assert by_frame["[X] focal frame."].score > by_frame["[X] common frame."].score
    assert "[X] focal frame." not in {row.frame for row in result.recurrence_ranking if row.df_bg}


@pytest.mark.asyncio
async def test_phrase_stats_reports_empty_background(phrase_stats_session) -> None:
    session = phrase_stats_session
    license_row = License(
        code=f"TEST-{uuid4().hex[:12]}",
        name="Self-authored integration-test license",
        allows_mining=True,
        allows_display=True,
    )
    session.add(license_row)
    await session.flush()
    focal_batch = uuid4()
    _, sentence_id = await _article(session, license_row.id, focal_batch)
    await _candidate(session, sentence_id, "[X] only focal.")
    await session.commit()

    result = compute_phrase_stats(
        await candidate_articles(session),
        PhraseStatsRequest(focal_batch_id=focal_batch, all_other=True),
        load_policy_bundle().phrase_stats,
    )

    assert result.n_bg == 0
    assert result.score_ranking == ()
    assert any("background is empty" in notice for notice in result.notices)
