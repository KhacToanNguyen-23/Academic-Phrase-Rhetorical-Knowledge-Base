"""Persistence queries for proposal and confirmed candidate labels."""

from collections import defaultdict
from typing import Any, cast
from uuid import UUID

from sqlalchemy import any_, case, desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.corpus.models import Article, Sentence
from aprkb.modules.mining.label_merge import MergedFrameLabel
from aprkb.modules.mining.models import Candidate, CandidateLabel


async def labels_for_candidates(
    session: AsyncSession, candidate_ids: list[UUID]
) -> dict[UUID, list[dict[str, Any]]]:
    if not candidate_ids:
        return {}
    rows = await session.scalars(
        select(CandidateLabel)
        .where(CandidateLabel.candidate_id.in_(candidate_ids))
        .order_by(CandidateLabel.candidate_id, CandidateLabel.label_code)
    )
    result: defaultdict[UUID, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[row.candidate_id].append(
            {
                "label_code": row.label_code,
                "value": row.value,
                "status": row.status,
                "source": row.source,
                "confidence": row.confidence,
                "options": row.options,
                "evidence": row.evidence,
                "needs_attention": row.needs_attention,
                "agreement": row.agreement,
            }
        )
    return dict(result)


async def upsert_proposals(
    session: AsyncSession,
    *,
    candidate_id: UUID,
    labels: list[MergedFrameLabel],
    run_id: str,
) -> int:
    """Upsert drafts but preserve both confirmed and rejected human decisions."""
    saved = 0
    for label in labels:
        statement = proposal_upsert_statement(candidate_id, label, run_id=run_id)
        result = await session.execute(statement)
        saved += int(cast(CursorResult[Any], result).rowcount or 0)
    return saved


def proposal_upsert_statement(candidate_id: UUID, label: MergedFrameLabel, *, run_id: str) -> Any:
    statement = insert(CandidateLabel).values(
        candidate_id=candidate_id,
        label_code=label.label_code,
        value=label.value,
        status="proposed",
        source=label.source,
        confidence=label.confidence,
        options=label.options,
        evidence=label.evidence,
        needs_attention=label.needs_attention,
        agreement=label.agreement,
        proposed_by_run=run_id,
    )
    return statement.on_conflict_do_update(
        constraint="uq_candidate_labels_candidate_code",
        set_={
            "value": statement.excluded.value,
            "status": "proposed",
            "source": statement.excluded.source,
            "confidence": statement.excluded.confidence,
            "options": statement.excluded.options,
            "needs_attention": statement.excluded.needs_attention,
            "agreement": statement.excluded.agreement,
            "proposed_by_run": run_id,
            "updated_at": statement.excluded.updated_at,
        },
        where=CandidateLabel.status == "proposed",
    )


async def review_candidate_page(
    session: AsyncSession,
    *,
    label_code: str | None,
    min_confidence: float | None,
    needs_attention: bool | None,
    agreement: str | None,
    paper_count: int | None,
    offset: int,
    limit: int,
) -> tuple[list[tuple[UUID, int]], int]:
    paper_count_expr = (
        select(func.count(func.distinct(Article.id)))
        .select_from(Sentence)
        .join(Article, Article.id == Sentence.article_id)
        .where(Sentence.id == any_(Candidate.source_sentence_ids))
        .correlate(Candidate)
        .scalar_subquery()
    )
    clauses = [CandidateLabel.status == "proposed"]
    if label_code is not None:
        clauses.append(CandidateLabel.label_code == label_code)
    if min_confidence is not None:
        clauses.append(CandidateLabel.confidence >= min_confidence)
    if needs_attention is not None:
        clauses.append(CandidateLabel.needs_attention.is_(needs_attention))
    if agreement is not None:
        clauses.append(CandidateLabel.agreement == agreement)
    if paper_count is not None:
        clauses.append(paper_count_expr == paper_count)
    total = int(
        await session.scalar(
            select(func.count(func.distinct(Candidate.id)))
            .select_from(Candidate)
            .join(CandidateLabel, CandidateLabel.candidate_id == Candidate.id)
            .where(*clauses)
        )
        or 0
    )
    attention_order = func.max(case((CandidateLabel.needs_attention.is_(True), 1), else_=0))
    rows = await session.execute(
        select(Candidate.id, paper_count_expr)
        .join(CandidateLabel, CandidateLabel.candidate_id == Candidate.id)
        .where(*clauses)
        .group_by(Candidate.id, paper_count_expr)
        .order_by(desc(attention_order), Candidate.id)
        .offset(offset)
        .limit(limit)
    )
    return [(candidate_id, int(count or 0)) for candidate_id, count in rows], total


async def lock_candidate_label(
    session: AsyncSession, *, candidate_id: UUID, label_code: str
) -> CandidateLabel | None:
    return await session.scalar(
        select(CandidateLabel)
        .where(
            CandidateLabel.candidate_id == candidate_id,
            CandidateLabel.label_code == label_code,
        )
        .with_for_update()
    )
