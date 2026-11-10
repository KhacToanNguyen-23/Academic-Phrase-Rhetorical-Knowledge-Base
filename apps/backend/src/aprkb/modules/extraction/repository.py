"""Queries for batches, articles, source text and mined phrases."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, String, any_, cast, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.journals.models import JournalProfile
from aprkb.modules.mining.models import Candidate, Job
from aprkb.modules.taxonomy.models import ArticleGenre

MINE_JOB_TYPE = "mine_article"


@dataclass(frozen=True)
class SourceRow:
    sentence_id: UUID
    article_id: UUID
    text: str
    section_code: str | None
    article_title: str | None
    journal: str | None
    allows_mining: bool
    license_code: str
    allows_display: bool
    genre_code: str | None
    journal_id: UUID | None


def article_scope(
    *, article_ids: list[UUID], batch_ids: list[UUID], unbatched: bool
) -> ColumnElement[bool] | None:
    """Return the article filter for the selected scope, or None when nothing is selected."""
    parts: list[ColumnElement[bool]] = []
    if article_ids:
        parts.append(Article.id.in_(article_ids))
    if batch_ids:
        parts.append(Article.import_batch_id.in_(batch_ids))
    if unbatched:
        parts.append(Article.import_batch_id.is_(None))
    return or_(*parts) if parts else None


def _mine_job_exists(status: str) -> ColumnElement[bool]:
    return exists().where(
        Job.type == MINE_JOB_TYPE,
        Job.status == status,
        Job.payload["article_id"].as_string() == cast(Article.id, String),
    )


async def list_batches(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(
                Article.import_batch_id,
                func.min(Article.created_at).label("imported_at"),
                func.count(Article.id).label("articles"),
                func.count(Article.id).filter(Article.ingest_status == "ready").label("ready"),
                func.count(Article.id).filter(_mine_job_exists("succeeded")).label("mined"),
            )
            .group_by(Article.import_batch_id)
            .order_by(func.min(Article.created_at).desc())
        )
    ).all()
    counts: dict[UUID | None, dict[str, int]] = defaultdict(dict)
    for batch_id, status, total in (
        await session.execute(
            select(
                Article.import_batch_id,
                Candidate.status,
                func.count(func.distinct(Candidate.id)),
            )
            .select_from(Candidate)
            .join(Sentence, Sentence.id == any_(Candidate.source_sentence_ids))
            .join(Article, Article.id == Sentence.article_id)
            .group_by(Article.import_batch_id, Candidate.status)
        )
    ).all():
        counts[batch_id][status] = total
    return [
        {
            "batch_id": row.import_batch_id,
            "imported_at": row.imported_at,
            "articles": row.articles,
            "ready": row.ready,
            "mined": row.mined,
            "phrases": counts.get(row.import_batch_id, {}),
        }
        for row in rows
    ]


async def list_articles(
    session: AsyncSession, scope: ColumnElement[bool] | None
) -> list[dict[str, Any]]:
    query = (
        select(Article, JournalProfile.name)
        .outerjoin(JournalProfile, JournalProfile.id == Article.journal_id)
        .order_by(Article.created_at.desc(), Article.id)
    )
    if scope is not None:
        query = query.where(scope)
    articles = list((await session.execute(query)).all())
    ids = [article.id for article, _ in articles]
    mining = await latest_mining_status(session, ids)
    counts = await phrase_counts_by_article(session, ids)
    return [
        {
            "id": article.id,
            "title": article.title,
            "doi": article.doi,
            "journal": journal or None,
            "batch_id": article.import_batch_id,
            "ingest_status": article.ingest_status,
            "mining_status": mining.get(article.id, "not_started"),
            "phrases": counts.get(article.id, {}),
        }
        for article, journal in articles
    ]


async def latest_mining_status(session: AsyncSession, article_ids: list[UUID]) -> dict[UUID, str]:
    if not article_ids:
        return {}
    id_text = Job.payload["article_id"].as_string()
    rows = (
        await session.execute(
            select(id_text, Job.status)
            .where(Job.type == MINE_JOB_TYPE, id_text.in_([str(i) for i in article_ids]))
            .order_by(Job.created_at)
        )
    ).all()
    latest: dict[UUID, str] = {}
    for article_id, status in rows:
        latest[UUID(article_id)] = status
    return latest


async def phrase_counts_by_article(
    session: AsyncSession, article_ids: list[UUID]
) -> dict[UUID, dict[str, int]]:
    if not article_ids:
        return {}
    result: dict[UUID, dict[str, int]] = defaultdict(dict)
    for article_id, status, total in (
        await session.execute(
            select(Sentence.article_id, Candidate.status, func.count(func.distinct(Candidate.id)))
            .select_from(Candidate)
            .join(Sentence, Sentence.id == any_(Candidate.source_sentence_ids))
            .where(Sentence.article_id.in_(article_ids))
            .group_by(Sentence.article_id, Candidate.status)
        )
    ).all():
        result[article_id][status] = total
    return result


async def get_article_with_license(
    session: AsyncSession, article_id: UUID
) -> tuple[Article, bool] | None:
    row = (
        await session.execute(
            select(Article, License.allows_mining)
            .join(License, License.id == Article.license_id)
            .where(Article.id == article_id)
        )
    ).first()
    return (row[0], bool(row[1])) if row else None


async def article_sentences(
    session: AsyncSession, article_id: UUID
) -> list[tuple[UUID, str, str | None, str | None, int | None]]:
    rows = (
        await session.execute(
            select(
                Sentence.id,
                Sentence.text,
                ArticleSection.heading,
                ArticleSection.section_code,
                ArticleSection.order,
            )
            .outerjoin(ArticleSection, ArticleSection.id == Sentence.article_section_id)
            .where(Sentence.article_id == article_id)
            .order_by(ArticleSection.order.nulls_last(), Sentence.char_start, Sentence.id)
        )
    ).all()
    return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]


def phrase_filter(status: str, scope: ColumnElement[bool] | None) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = [Candidate.status == status]
    if scope is not None:
        clauses.append(
            select(Sentence.id)
            .join(Article, Article.id == Sentence.article_id)
            .where(Sentence.id == any_(Candidate.source_sentence_ids), scope)
            .exists()
        )
    return clauses


async def list_phrases(
    session: AsyncSession,
    *,
    status: str,
    scope: ColumnElement[bool] | None,
    limit: int,
    offset: int,
) -> tuple[list[Candidate], int]:
    clauses = phrase_filter(status, scope)
    total = await count_phrases(session, status=status, scope=scope)
    items = list(
        await session.scalars(
            select(Candidate)
            .where(*clauses)
            .order_by(Candidate.created_at, Candidate.id)
            .limit(limit)
            .offset(offset)
        )
    )
    return items, int(total or 0)


async def count_phrases(
    session: AsyncSession, *, status: str, scope: ColumnElement[bool] | None
) -> int:
    total = await session.scalar(
        select(func.count()).select_from(Candidate).where(*phrase_filter(status, scope))
    )
    return int(total or 0)


async def source_rows(session: AsyncSession, sentence_ids: list[UUID]) -> dict[UUID, SourceRow]:
    if not sentence_ids:
        return {}
    rows = (
        await session.execute(
            select(
                Sentence.id,
                Sentence.article_id,
                Sentence.text,
                ArticleSection.section_code,
                Article.title,
                JournalProfile.name,
                License.allows_mining,
                License.code,
                License.allows_display,
                ArticleGenre.code,
                Article.journal_id,
            )
            .join(Article, Article.id == Sentence.article_id)
            .join(License, License.id == Article.license_id)
            .outerjoin(ArticleSection, ArticleSection.id == Sentence.article_section_id)
            .outerjoin(JournalProfile, JournalProfile.id == Article.journal_id)
            .outerjoin(ArticleGenre, ArticleGenre.id == Article.genre_id)
            .where(Sentence.id.in_(sentence_ids))
        )
    ).all()
    return {
        row[0]: SourceRow(
            sentence_id=row[0],
            article_id=row[1],
            text=row[2],
            section_code=row[3],
            article_title=row[4],
            journal=row[5],
            allows_mining=bool(row[6]),
            license_code=row[7],
            allows_display=bool(row[8]),
            genre_code=row[9],
            journal_id=row[10],
        )
        for row in rows
    }


async def candidate_section_sources(
    session: AsyncSession, candidate_ids: list[UUID]
) -> dict[UUID, list[tuple[UUID, str | None]]]:
    """Read allowed source article IDs and section codes without selecting sentence text."""
    if not candidate_ids:
        return {}
    rows = (
        await session.execute(
            select(Candidate.id, Article.id, ArticleSection.section_code)
            .join(Sentence, Sentence.id == any_(Candidate.source_sentence_ids))
            .join(Article, Article.id == Sentence.article_id)
            .join(License, License.id == Article.license_id)
            .outerjoin(ArticleSection, ArticleSection.id == Sentence.article_section_id)
            .where(Candidate.id.in_(candidate_ids), License.allows_mining.is_(True))
            .order_by(Candidate.id, Article.id, Sentence.id)
        )
    ).all()
    sources: defaultdict[UUID, list[tuple[UUID, str | None]]] = defaultdict(list)
    for candidate_id, article_id, section_code in rows:
        sources[candidate_id].append((article_id, section_code))
    return dict(sources)
