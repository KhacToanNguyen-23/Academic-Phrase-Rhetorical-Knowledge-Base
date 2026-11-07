"""Extraction page use cases: scoped bulk mining, safe phrase listing, one-reviewer decisions.

Accepting a phrase stores it in ``approved_phrases``; it never creates a PhrasePattern, so it
needs no intent and does not feed recommendations. Provenance and licence are rechecked at
decision time (fail closed), and no article text is written to the audit trail.
"""

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.logging import get_logger
from aprkb.modules.audit.service import record_event
from aprkb.modules.corpus.models import Article
from aprkb.modules.corpus.service import enqueue_mining
from aprkb.modules.extraction import repository
from aprkb.modules.extraction.models import ApprovedPhrase
from aprkb.modules.extraction.schemas import (
    MAX_MINE_ARTICLES,
    ArticleTextRead,
    BulkDecisionCreate,
    BulkDecisionFailure,
    BulkDecisionResult,
    MineRequest,
    MineResult,
    PhraseDecisionCreate,
    PhraseDecisionResult,
    PhrasePage,
    PhraseRead,
    PhraseSource,
    SectionText,
    SentenceText,
)
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.models import Candidate
from aprkb.modules.mining.schemas import SlotDefinition, is_safe_masked_frame
from aprkb.modules.review.repository import lock_candidate
from aprkb.policies.loader import load_policy_bundle

logger = get_logger(__name__)
_REPORTING_FORMS = load_policy_bundle().reporting_verbs.all_forms


async def article_text(session: AsyncSession, article_id: UUID) -> ArticleTextRead:
    found = await repository.get_article_with_license(session, article_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article, allows_mining = found
    # Fail closed: the same mining right that gates the pipeline gates reading the text here.
    if not allows_mining:
        raise HTTPException(status_code=403, detail="Article license does not allow mining")
    sections: dict[int | None, SectionText] = {}
    for sentence_id, text, heading, code, order, page_number in await repository.article_sentences(
        session, article_id
    ):
        section = sections.setdefault(
            order,
            SectionText(heading=heading, section_code=code, sentences=[], page_number=page_number),
        )
        section.sentences.append(SentenceText(id=sentence_id, text=text))
    return ArticleTextRead(
        article_id=article.id, title=article.title, sections=list(sections.values())
    )


async def mine_scope(
    session: AsyncSession,
    *,
    payload: MineRequest,
    actor: ApiClient,
    request_id: str,
) -> MineResult:
    scope = repository.article_scope(
        article_ids=payload.article_ids, batch_ids=payload.batch_ids, unbatched=payload.unbatched
    )
    rows = (
        await session.execute(
            select(Article.id, Article.ingest_status)
            .where(_required(scope))
            .order_by(Article.created_at, Article.id)
        )
    ).all()
    if len(rows) > MAX_MINE_ARTICLES:
        raise HTTPException(
            status_code=422,
            detail=f"At most {MAX_MINE_ARTICLES} articles can be mined per request",
        )
    job_ids: list[UUID] = []
    skipped = 0
    for article_id, ingest_status in rows:
        if ingest_status != "ready":
            skipped += 1
            continue
        try:
            job = await enqueue_mining(
                session, article_id=article_id, actor=actor, request_id=request_id
            )
        except HTTPException:
            skipped += 1
            continue
        job_ids.append(job.id)
    return MineResult(job_ids=job_ids, articles=len(rows), skipped_not_ready=skipped)


async def list_phrases(
    session: AsyncSession,
    *,
    status: str,
    scope: ColumnElement[bool] | None,
    limit: int,
    offset: int,
) -> PhrasePage:
    candidates, total = await repository.list_phrases(
        session, status=status, scope=scope, limit=limit, offset=offset
    )
    sentence_ids = sorted({sid for item in candidates for sid in item.source_sentence_ids})
    rows = await repository.source_rows(session, sentence_ids)
    return PhrasePage(items=[_to_phrase(item, rows) for item in candidates], total=total)


def _required(scope: ColumnElement[bool] | None) -> ColumnElement[bool]:
    if scope is None:
        raise HTTPException(status_code=422, detail="Select at least one article or batch")
    return scope


def _typed_slots(candidate: Candidate) -> dict[str, SlotDefinition] | None:
    if not isinstance(candidate.slots, dict) or set(candidate.slots) - {"X", "Y", "Z"}:
        return None
    try:
        return {
            name: SlotDefinition.model_validate(value) for name, value in candidate.slots.items()
        }
    except (TypeError, ValueError, ValidationError):
        return None


def _is_safe(candidate: Candidate) -> bool:
    return _typed_slots(candidate) is not None and is_safe_masked_frame(
        candidate.canonical_frame, _REPORTING_FORMS
    )


def _relative_spans(candidate: Candidate, sentence_id: UUID) -> dict[str, tuple[int, int]]:
    """Slot ranges relative to the sentence text; stored offsets are relative to the section."""
    for occurrence in candidate.occurrences or []:
        if occurrence.get("sentence_id") != str(sentence_id):
            continue
        base = occurrence.get("sentence_start")
        spans = occurrence.get("slot_spans")
        if not isinstance(base, int) or not isinstance(spans, dict):
            return {}
        try:
            return {
                name: (int(span[0]) - base, int(span[1]) - base) for name, span in spans.items()
            }
        except (TypeError, ValueError, IndexError):
            return {}
    return {}


def _to_phrase(candidate: Candidate, rows: dict[UUID, repository.SourceRow]) -> PhraseRead:
    sources: list[PhraseSource] = []
    blocked = not candidate.source_sentence_ids or not _is_safe(candidate)
    for sentence_id in candidate.source_sentence_ids:
        row = rows.get(sentence_id)
        if row is None or not row.allows_mining:
            blocked = True
            continue
        sources.append(
            PhraseSource(
                sentence_id=row.sentence_id,
                article_id=row.article_id,
                article_title=row.article_title,
                journal=row.journal,
                section=row.section_code,
                text=row.text,
                slot_spans=_relative_spans(candidate, sentence_id),
            )
        )
    return PhraseRead(
        id=candidate.id,
        canonical_frame=candidate.canonical_frame,
        slots=_typed_slots(candidate) or {},
        epistemic_strength=candidate.epistemic_strength,
        status=candidate.status,
        blocked=blocked,
        sources=sources,
    )


async def decide_phrase(
    session: AsyncSession,
    *,
    candidate_id: UUID,
    payload: PhraseDecisionCreate,
    reviewer: ApiClient,
    request_id: str,
) -> PhraseDecisionResult:
    try:
        result = await _decide(
            session,
            candidate_id=candidate_id,
            decision=payload.decision,
            comment=payload.comment,
            reviewer=reviewer,
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return result


async def decide_many(
    session: AsyncSession,
    *,
    payload: BulkDecisionCreate,
    reviewer: ApiClient,
    request_id: str,
) -> BulkDecisionResult:
    results: list[PhraseDecisionResult] = []
    failed: list[BulkDecisionFailure] = []
    try:
        for candidate_id in dict.fromkeys(payload.candidate_ids):
            try:
                # A savepoint per phrase: one unsafe phrase must not undo the others.
                async with session.begin_nested():
                    results.append(
                        await _decide(
                            session,
                            candidate_id=candidate_id,
                            decision=payload.decision,
                            comment=payload.comment,
                            reviewer=reviewer,
                            request_id=request_id,
                        )
                    )
            except HTTPException as error:
                failed.append(
                    BulkDecisionFailure(candidate_id=candidate_id, reason=str(error.detail))
                )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return BulkDecisionResult(results=results, failed=failed)


async def _decide(
    session: AsyncSession,
    *,
    candidate_id: UUID,
    decision: str,
    comment: str | None,
    reviewer: ApiClient,
    request_id: str,
) -> PhraseDecisionResult:
    candidate = await lock_candidate(session, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Phrase not found")
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail="Phrase is no longer pending")
    before = {"status": candidate.status}
    approved_id: UUID | None = None
    after: dict[str, Any]
    if decision == "accept":
        approved = await _approve(session, candidate, reviewer, comment)
        approved_id = approved.id
        candidate.status = "accepted"
        after = {
            "status": "accepted",
            "approved_phrase_id": str(approved.id),
            "article_id": str(approved.article_id) if approved.article_id else None,
            "journal_id": str(approved.journal_id) if approved.journal_id else None,
        }
    else:
        candidate.status = "rejected"
        after = {"status": "rejected"}
    await session.flush()
    await record_event(
        session,
        actor_id=reviewer.id,
        action=f"extraction.phrase.{decision}",
        entity_type="candidate",
        entity_id=candidate.id,
        before=before,
        after=after,
        request_id=request_id,
    )
    return PhraseDecisionResult(
        candidate_id=candidate.id, status=candidate.status, approved_phrase_id=approved_id
    )


async def _approve(
    session: AsyncSession, candidate: Candidate, reviewer: ApiClient, comment: str | None
) -> ApprovedPhrase:
    if not _is_safe(candidate):
        raise HTTPException(status_code=409, detail="Phrase abstraction schema is invalid")
    sentence_ids = candidate.source_sentence_ids
    if not sentence_ids or len(set(sentence_ids)) != len(sentence_ids):
        raise HTTPException(status_code=409, detail="Phrase has no source sentences")
    rows = await repository.source_rows(session, list(sentence_ids))
    if len(rows) != len(sentence_ids) or any(not row.allows_mining for row in rows.values()):
        raise HTTPException(status_code=409, detail="Phrase provenance is missing or not licensed")
    articles = {row.article_id for row in rows.values()}
    journals = {row.journal_id for row in rows.values()}
    approved = ApprovedPhrase(
        candidate_id=candidate.id,
        canonical_frame=candidate.canonical_frame,
        slots=candidate.slots,
        epistemic_strength=candidate.epistemic_strength,
        cluster_key=candidate.cluster_key,
        article_id=next(iter(articles)) if len(articles) == 1 else None,
        journal_id=next(iter(journals)) if len(journals) == 1 else None,
        source_sentence_ids=list(sentence_ids),
        comment=comment,
        created_by=reviewer.id,
    )
    session.add(approved)
    await session.flush()
    return approved
