from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import selectinload

from aprkb.modules.audit.models import AuditEvent
from aprkb.modules.vocabulary.models import VocabLemma
from aprkb.modules.vocabulary.service import import_workbook
from aprkb.policies.loader import load_policy_bundle


def _workbook(coca_all: int, *, word: str = "SelfAuthored") -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "list"
    worksheet.append(
        ["ID", "band", "status", "word", "Pos", "COCA-All", "COCA-Acad", "ratio", "disp", "range"]
    )
    worksheet.append([1, 1, "y", word, "n", coca_all, 5, 1.1, 0.5, 2])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _family_workbook() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "data"
    worksheet.append(
        ["famRank", "family", "famFreq", "word", "PoS", "freq", "ratio", "categ", "domain"]
    )
    worksheet.append([1, "Run", 14, "run", "n", 10, 1.0, "y", "Sci+Fin"])
    worksheet.append([1, "Run", 14, "runner", "n", 4, 0.5, "x", "Fin"])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _acad_core_workbook() -> bytes:
    domains = ["HIS", "EDU", "SOC", "LAW", "HUM", "PHIL", "SCI", "MED", "BUS"]
    headers = ["ID", "word", "PoS", "COCA-All", "COCA-Acad", "ratio", "disp", "range"]
    values: list[object] = [7, "run", "n", 100, 90, 1.2, 0.5, 3]
    for domain in domains:
        headers.extend([domain, domain])
        values.extend([1, 0.1])
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "list"
    worksheet.append(headers)
    worksheet.append(values)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


@pytest.mark.asyncio
async def test_all_words_import_is_idempotent_and_audited(
    postgres_test_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    policy = load_policy_bundle().vocabulary_import
    async with factory() as session:
        first = await import_workbook(
            session,
            content=_workbook(10),
            filename="self-authored.xlsx",
            actor=None,
            request_id="test-vocabulary-import",
            policy=policy,
        )
        second = await import_workbook(
            session,
            content=_workbook(11),
            filename="self-authored.xlsx",
            actor=None,
            request_id="test-vocabulary-import",
            policy=policy,
        )
        assert first.inserted == 1
        assert second.inserted == 0
        assert second.updated == 1
        lemma = await session.scalar(select(VocabLemma).where(VocabLemma.word == "selfauthored"))
        assert lemma is not None and lemma.coca_all == 11
        audit = await session.scalar(
            select(AuditEvent)
            .where(AuditEvent.action == "vocabulary.import")
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit is not None
        assert "SelfAuthored" not in str(audit.after)


@pytest.mark.asyncio
async def test_vocabulary_sources_preserve_source_owned_fields(
    postgres_test_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    policy = load_policy_bundle().vocabulary_import
    async with factory() as session:
        families = await import_workbook(
            session,
            content=_family_workbook(),
            filename="families.xlsx",
            actor=None,
            request_id="test-vocabulary-families",
            policy=policy,
        )
        assert families.source_kind == "families"
        run = await session.scalar(select(VocabLemma).where(VocabLemma.word == "run"))
        assert run is not None
        assert run.rank is None
        assert run.domains == ["BUS", "SCI"]

        all_words = await import_workbook(
            session,
            content=_workbook(10, word="Run"),
            filename="allWords.xlsx",
            actor=None,
            request_id="test-vocabulary-all-words",
            policy=policy,
        )
        assert all_words.source_kind == "all_words"

        acad_core = await import_workbook(
            session,
            content=_acad_core_workbook(),
            filename="acadCore.xlsx",
            actor=None,
            request_id="test-vocabulary-acad-core",
            policy=policy,
        )
        assert acad_core.source_kind == "acad_core"
        # The import upserts through Core statements, so refresh the already-loaded ORM object.
        run = await session.scalar(
            select(VocabLemma)
            .where(VocabLemma.word == "run")
            .options(selectinload(VocabLemma.domain_stats))
            .execution_options(populate_existing=True)
        )
        assert run is not None
        assert run.is_core is True
        assert run.rank == 7
        assert run.domains == ["BUS", "SCI"]
        assert run.band == 1
        assert run.status == "y"
        assert len(run.domain_stats) == 9
        assert (
            await session.scalar(select(VocabLemma).where(VocabLemma.word == "runner")) is not None
        )
