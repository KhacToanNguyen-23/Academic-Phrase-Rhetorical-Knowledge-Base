"""Bulk persistence operations for vocabulary imports and reads."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Integer, func, literal_column, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aprkb.modules.vocabulary.models import (
    VocabFamily,
    VocabFamilyMember,
    VocabImportRun,
    VocabLemma,
    VocabLemmaDomainStat,
    VocabLemmaResearchStat,
    VocabResearchGroup,
)
from aprkb.modules.vocabulary.parsers import DomainStatRow, FamilyRow, LemmaRow, MemberRow

CHUNK_SIZE = 1000


@dataclass(frozen=True)
class UpsertCounts:
    inserted: int = 0
    updated: int = 0

    def add(self, other: UpsertCounts) -> UpsertCounts:
        return UpsertCounts(self.inserted + other.inserted, self.updated + other.updated)


def _count_returning(rows: Iterable[tuple[object, ...]]) -> UpsertCounts:
    inserted = 0
    updated = 0
    for row in rows:
        if bool(row[-1]):
            inserted += 1
        else:
            updated += 1
    return UpsertCounts(inserted, updated)


async def _upsert_lemmas(
    session: AsyncSession, rows: list[LemmaRow], *, source_kind: str
) -> UpsertCounts:
    total = UpsertCounts()
    for start in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[start : start + CHUNK_SIZE]
        values: list[dict[str, object]] = []
        for row in chunk:
            value: dict[str, object] = {"word": row.word, "pos": row.pos}
            if source_kind == "all_words":
                value.update(
                    rank=row.rank,
                    band=row.band,
                    status=row.status,
                    coca_all=row.coca_all,
                    coca_acad=row.coca_acad,
                    ratio=row.ratio,
                    disp=row.disp,
                    domain_range=row.range,
                )
            else:
                value.update(
                    rank=row.rank,
                    coca_all=row.coca_all,
                    coca_acad=row.coca_acad,
                    ratio=row.ratio,
                    disp=row.disp,
                    domain_range=row.range,
                    is_core=True,
                )
            values.append(value)
        statement = insert(VocabLemma).values(values)
        excluded = statement.excluded
        updates = (
            {
                "rank": excluded.rank,
                "band": excluded.band,
                "status": excluded.status,
                "coca_all": excluded.coca_all,
                "coca_acad": excluded.coca_acad,
                "ratio": excluded.ratio,
                "disp": excluded.disp,
                "range": excluded.range,
                "updated_at": func.now(),
            }
            if source_kind == "all_words"
            else {
                "rank": excluded.rank,
                "coca_all": excluded.coca_all,
                "coca_acad": excluded.coca_acad,
                "ratio": excluded.ratio,
                "disp": excluded.disp,
                "range": excluded.range,
                "is_core": True,
                "updated_at": func.now(),
            }
        )
        result: Result[Any] = await session.execute(
            statement.on_conflict_do_update(
                constraint="uq_vocab_lemmas_word_pos", set_=updates
            ).returning(VocabLemma.id, VocabLemma.word, VocabLemma.pos, literal_column("xmax = 0"))
        )
        total = total.add(_count_returning(result.all()))
    return total


async def _lemma_ids(
    session: AsyncSession, keys: Iterable[tuple[str, str]]
) -> dict[tuple[str, str], UUID]:
    pairs = list(dict.fromkeys(keys))
    if not pairs:
        return {}
    result: dict[tuple[str, str], UUID] = {}
    for start in range(0, len(pairs), CHUNK_SIZE):
        rows = await session.execute(
            select(VocabLemma.id, VocabLemma.word, VocabLemma.pos).where(
                tuple_(VocabLemma.word, VocabLemma.pos).in_(pairs[start : start + CHUNK_SIZE])
            )
        )
        result.update({(word, pos): lemma_id for lemma_id, word, pos in rows.all()})
    return result


async def _upsert_domain_stats(
    session: AsyncSession, rows: list[DomainStatRow], lemma_ids: dict[tuple[str, str], UUID]
) -> UpsertCounts:
    values = [
        {
            "lemma_id": lemma_ids[(row.word, row.pos)],
            "domain": row.domain,
            "freq": row.freq,
            "relative_ratio": row.relative_ratio,
        }
        for row in rows
    ]
    total = UpsertCounts()
    for start in range(0, len(values), CHUNK_SIZE):
        statement = insert(VocabLemmaDomainStat).values(values[start : start + CHUNK_SIZE])
        excluded = statement.excluded
        result: Result[Any] = await session.execute(
            statement.on_conflict_do_update(
                constraint="uq_vocab_domain_stats_lemma_domain",
                set_={"freq": excluded.freq, "relative_ratio": excluded.relative_ratio},
            ).returning(VocabLemmaDomainStat.id, literal_column("xmax = 0"))
        )
        total = total.add(_count_returning(result.all()))
    return total


async def _upsert_families(
    session: AsyncSession, rows: list[FamilyRow]
) -> tuple[UpsertCounts, dict[str, UUID]]:
    total = UpsertCounts()
    for start in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[start : start + CHUNK_SIZE]
        statement = insert(VocabFamily).values(
            [
                {"headword": row.headword, "rank": row.rank, "family_freq": row.family_freq}
                for row in chunk
            ]
        )
        excluded = statement.excluded
        result: Result[Any] = await session.execute(
            statement.on_conflict_do_update(
                index_elements=[VocabFamily.headword],
                set_={
                    "rank": excluded.rank,
                    "family_freq": excluded.family_freq,
                    "updated_at": func.now(),
                },
            ).returning(VocabFamily.id, VocabFamily.headword, literal_column("xmax = 0"))
        )
        total = total.add(_count_returning(result.all()))
    family_ids = {
        headword: family_id
        for family_id, headword in (
            await session.execute(
                select(VocabFamily.id, VocabFamily.headword).where(
                    VocabFamily.headword.in_([row.headword for row in rows])
                )
            )
        ).all()
    }
    return total, family_ids


async def _upsert_family_members(
    session: AsyncSession,
    rows: list[MemberRow],
    lemma_ids: dict[tuple[str, str], UUID],
    family_ids: dict[str, UUID],
) -> UpsertCounts:
    values = [
        {
            "family_id": family_ids[row.headword],
            "lemma_id": lemma_ids[(row.word, row.pos)],
            "freq": row.freq,
            "category": row.category,
        }
        for row in rows
    ]
    total = UpsertCounts()
    for start in range(0, len(values), CHUNK_SIZE):
        statement = insert(VocabFamilyMember).values(values[start : start + CHUNK_SIZE])
        excluded = statement.excluded
        result: Result[Any] = await session.execute(
            statement.on_conflict_do_update(
                constraint="uq_vocab_family_members_family_lemma",
                set_={"freq": excluded.freq, "category": excluded.category},
            ).returning(VocabFamilyMember.id, literal_column("xmax = 0"))
        )
        total = total.add(_count_returning(result.all()))
    return total


async def upsert_lemmas(
    session: AsyncSession, rows: list[LemmaRow], *, source_kind: str
) -> UpsertCounts:
    return await _upsert_lemmas(session, rows, source_kind=source_kind)


async def upsert_acad_core(
    session: AsyncSession, lemmas: list[LemmaRow], domain_stats: list[DomainStatRow]
) -> UpsertCounts:
    counts = await _upsert_lemmas(session, lemmas, source_kind="acad_core")
    ids = await _lemma_ids(session, [(row.word, row.pos) for row in lemmas])
    return counts.add(await _upsert_domain_stats(session, domain_stats, ids))


async def upsert_families(
    session: AsyncSession, families: list[FamilyRow], members: list[MemberRow]
) -> UpsertCounts:
    family_counts, family_ids = await _upsert_families(session, families)
    domains_by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in members:
        domains_by_key[(row.word, row.pos)].update(row.domains)
    lemma_values = [
        {"word": word, "pos": pos, "domains": sorted(domains)}
        for (word, pos), domains in domains_by_key.items()
    ]
    lemma_counts = UpsertCounts()
    for start in range(0, len(lemma_values), CHUNK_SIZE):
        statement = insert(VocabLemma).values(lemma_values[start : start + CHUNK_SIZE])
        excluded = statement.excluded
        result: Result[Any] = await session.execute(
            statement.on_conflict_do_update(
                constraint="uq_vocab_lemmas_word_pos", set_={"domains": excluded.domains}
            ).returning(VocabLemma.id, literal_column("xmax = 0"))
        )
        lemma_counts = lemma_counts.add(_count_returning(result.all()))
    ids = await _lemma_ids(session, domains_by_key)
    member_counts = await _upsert_family_members(session, members, ids, family_ids)
    return family_counts.add(lemma_counts).add(member_counts)


async def list_import_runs(
    session: AsyncSession, *, limit: int, offset: int
) -> tuple[list[VocabImportRun], int]:
    total = int(await session.scalar(select(func.count()).select_from(VocabImportRun)) or 0)
    items = list(
        await session.scalars(
            select(VocabImportRun)
            .order_by(VocabImportRun.created_at.desc(), VocabImportRun.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


def _prefix(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class LemmaFilters:
    core_only: bool = False
    pos: str | None = None
    status: str | None = None
    band_min: int | None = None
    band_max: int | None = None
    domain: str | None = None
    research_group: str | None = None


def _lemma_filters(
    filters: LemmaFilters, *, q: str | None = None, letter: str | None = None
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if q:
        clauses.append(VocabLemma.word.like(f"{_prefix(q.strip().lower())}%", escape="\\"))
    if letter == "#":
        clauses.append(
            ~or_(*(VocabLemma.word.ilike(f"{value}%") for value in "abcdefghijklmnopqrstuvwxyz"))
        )
    elif letter:
        clauses.append(VocabLemma.word.like(f"{_prefix(letter.lower())}%", escape="\\"))
    if filters.core_only:
        clauses.append(VocabLemma.is_core.is_(True))
    if filters.pos is not None:
        clauses.append(VocabLemma.pos == filters.pos)
    if filters.status == "unknown":
        clauses.append(or_(VocabLemma.status.is_(None), VocabLemma.status == ""))
    elif filters.status is not None:
        clauses.append(VocabLemma.status == filters.status)
    if filters.band_min is not None:
        clauses.append(VocabLemma.band >= filters.band_min)
    if filters.band_max is not None:
        clauses.append(VocabLemma.band <= filters.band_max)
    if filters.domain is not None:
        clauses.append(
            VocabLemma.domain_stats.any(
                (VocabLemmaDomainStat.domain == filters.domain)
                & (VocabLemmaDomainStat.relative_ratio > 1.0)
            )
        )
    if filters.research_group is not None:
        clauses.append(
            select(VocabLemmaResearchStat.lemma_id)
            .where(
                VocabLemmaResearchStat.lemma_id == VocabLemma.id,
                VocabLemmaResearchStat.group_key == filters.research_group,
            )
            .correlate(VocabLemma)
            .exists()
        )
    return clauses


async def list_lemmas(
    session: AsyncSession,
    *,
    q: str | None,
    letter: str | None,
    filters: LemmaFilters,
    sort: str,
    limit: int,
    offset: int,
) -> tuple[list[tuple[VocabLemma, int | None, int | None]], int]:
    clauses = _lemma_filters(filters, q=q, letter=letter)
    total = int(
        await session.scalar(select(func.count()).select_from(VocabLemma).where(*clauses)) or 0
    )
    ordering = {
        "rank": (VocabLemma.rank.asc().nulls_last(),),
        "academic_frequency": (VocabLemma.coca_acad.desc().nulls_last(),),
    }.get(sort, ())
    paper_count: ColumnElement[int] = literal_column("NULL", Integer)
    sample_count: ColumnElement[int] = literal_column("NULL", Integer)
    if filters.research_group is not None:
        paper_count = (
            select(VocabLemmaResearchStat.paper_count)
            .where(
                VocabLemmaResearchStat.lemma_id == VocabLemma.id,
                VocabLemmaResearchStat.group_key == filters.research_group,
            )
            .scalar_subquery()
        )
        sample_count = (
            select(VocabResearchGroup.paper_count)
            .where(VocabResearchGroup.key == filters.research_group)
            .scalar_subquery()
        )
    rows = await session.execute(
        select(VocabLemma, paper_count, sample_count)
        .where(*clauses)
        .order_by(*ordering, VocabLemma.word, VocabLemma.pos)
        .limit(limit)
        .offset(offset)
    )
    return [(lemma, count, sample) for lemma, count, sample in rows], total


async def list_research_groups(session: AsyncSession) -> list[VocabResearchGroup]:
    return list(
        await session.scalars(
            select(VocabResearchGroup).order_by(
                VocabResearchGroup.field_name,
                VocabResearchGroup.subfield_name.asc().nulls_first(),
                VocabResearchGroup.key,
            )
        )
    )


async def list_families(
    session: AsyncSession,
    *,
    q: str | None,
    limit: int,
    offset: int,
) -> tuple[list[VocabFamily], int]:
    clauses: list[ColumnElement[bool]] = []
    if q:
        clauses.append(VocabFamily.headword.like(f"{_prefix(q.strip().lower())}%", escape="\\"))
    total = int(
        await session.scalar(select(func.count()).select_from(VocabFamily).where(*clauses)) or 0
    )
    items = list(
        await session.scalars(
            select(VocabFamily)
            .options(selectinload(VocabFamily.members).selectinload(VocabFamilyMember.lemma))
            .where(*clauses)
            .order_by(VocabFamily.headword)
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


async def letter_counts(session: AsyncSession, filters: LemmaFilters) -> dict[str, int]:
    clauses = _lemma_filters(filters)
    first_letter = func.lower(func.left(VocabLemma.word, literal_column("1")))
    rows = await session.execute(
        select(first_letter, func.count()).where(*clauses).group_by(first_letter)
    )
    counts = {letter: 0 for letter in "abcdefghijklmnopqrstuvwxyz#"}
    for first, count in rows.all():
        normalized = first if first in counts and first != "#" else "#"
        counts[normalized] += int(count)
    return counts


async def get_lemma(session: AsyncSession, lemma_id: UUID) -> VocabLemma | None:
    return await session.scalar(
        select(VocabLemma)
        .options(
            selectinload(VocabLemma.domain_stats),
            selectinload(VocabLemma.family_members)
            .selectinload(VocabFamilyMember.family)
            .selectinload(VocabFamily.members)
            .selectinload(VocabFamilyMember.lemma),
        )
        .where(VocabLemma.id == lemma_id)
    )
