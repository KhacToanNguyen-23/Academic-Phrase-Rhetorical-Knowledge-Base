from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import app as _app  # noqa: F401 - register ORM mappings
from aprkb.modules.corpus.models import Article, License, Sentence
from aprkb.modules.vocabulary.models import VocabLemma, VocabLemmaResearchStat, VocabResearchGroup
from aprkb.modules.vocabulary.research_builder import (
    ClassifiedPaper,
    ResearchManifest,
    build_research_snapshot,
)


def test_manifest_rejects_duplicate_articles_and_conflicting_taxonomy() -> None:
    first = ClassifiedPaper(
        article_id=uuid4(),
        field_id="27",
        field_name="Medicine",
        subfield_id="2730",
        subfield_name="Oncology",
    )
    second = ClassifiedPaper(
        article_id=uuid4(),
        field_id="17",
        field_name="Computer Science",
        subfield_id="1712",
        subfield_name="Software",
    )

    with pytest.raises(ValidationError, match="each local article must occur once"):
        ResearchManifest(papers=[first, second.model_copy(update={"article_id": first.article_id})])
    with pytest.raises(ValidationError, match="conflicting assignments for subfield"):
        ResearchManifest(
            papers=[first, second.model_copy(update={"subfield_id": first.subfield_id})]
        )


@pytest.mark.asyncio
async def test_rebuild_counts_documents_and_replaces_the_snapshot(
    postgres_test_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(postgres_test_engine)
    async with factory.begin() as session:
        verified = License(code="CC-BY", name="Verified test license", allows_mining=True)
        unverified = License(
            code="DEV-UNVERIFIED", name="Unverified test license", allows_mining=True
        )
        session.add_all([verified, unverified])
        await session.flush()
        session.add_all(
            [
                VocabLemma(word="therapy", pos="n"),
                VocabLemma(word="algorithm", pos="n"),
                VocabLemma(word="trial", pos="n"),
                VocabLemma(word="report", pos="n"),
                VocabLemma(word="report", pos="v"),
                VocabLemma(word="estimate", pos="v"),
                VocabLemma(word="dose", pos="n"),
            ]
        )
        papers = []
        for index, sentence in enumerate(
            [
                "Therapy therapy, trial, report, estimate, dose2.",
                "THERAPY trial report dose2.",
                "Algorithm, trial.",
                "Algorithm algorithm trial.",
                "Therapy.",
            ]
        ):
            article = Article(
                license_id=unverified.id if index == 4 else verified.id,
                blob_key=f"paper-{index}",
                ingest_status="ready",
            )
            session.add(article)
            await session.flush()
            session.add(
                Sentence(
                    article_id=article.id,
                    text=sentence,
                    char_start=0,
                    char_end=len(sentence),
                )
            )
            medicine = index < 2 or index == 4
            papers.append(
                ClassifiedPaper(
                    article_id=article.id,
                    field_id="27" if medicine else "17",
                    field_name="Medicine" if medicine else "Computer Science",
                    subfield_id="2730" if medicine else "1712",
                    subfield_name="Oncology" if medicine else "Software",
                )
            )

    async with factory.begin() as session:
        counts = await build_research_snapshot(session, ResearchManifest(papers=papers[:4]))
        assert counts == (4, 4)

    with pytest.raises(ValueError, match="no ready, rights-cleared text"):
        async with factory.begin() as session:
            await build_research_snapshot(session, ResearchManifest(papers=papers))

    async with factory.begin() as session:
        rows = await session.execute(
            select(
                VocabLemmaResearchStat.group_key,
                VocabLemma.word,
                VocabLemmaResearchStat.paper_count,
            ).join(VocabLemma, VocabLemma.id == VocabLemmaResearchStat.lemma_id)
        )
        assert set(rows) == {
            ("field:17", "algorithm", 2),
            ("subfield:1712", "algorithm", 2),
            ("field:27", "therapy", 2),
            ("subfield:2730", "therapy", 2),
        }
        assert set(await session.scalars(select(VocabResearchGroup.paper_count))) == {2}

    async with factory.begin() as session:
        no_subfields = [
            paper.model_copy(update={"subfield_id": None, "subfield_name": None})
            for paper in papers[:4]
        ]
        assert await build_research_snapshot(session, ResearchManifest(papers=no_subfields)) == (
            2,
            2,
        )

    async with factory() as session:
        assert set(await session.scalars(select(VocabLemmaResearchStat.group_key))) == {
            "field:17",
            "field:27",
        }
