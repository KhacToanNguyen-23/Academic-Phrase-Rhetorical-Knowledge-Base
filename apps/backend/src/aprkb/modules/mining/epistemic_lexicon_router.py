"""Curator API for inspecting and reviewing versioned epistemic lexicon entries."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.epistemic_lexicon_schemas import (
    EpistemicLexiconAuditRead,
    EpistemicLexiconEntryRead,
    EpistemicLexiconPage,
    EpistemicLexiconReview,
)
from aprkb.modules.mining.epistemic_lexicon_service import (
    EPISTEMIC_ENRICHMENT_JOB_TYPE,
    review_epistemic_entry,
)
from aprkb.modules.mining.models import Candidate, EpistemicLexiconAudit, EpistemicLexiconEntry, Job

router = APIRouter(prefix="/admin/mining/epistemic-lexicon", tags=["epistemic lexicon"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Reviewer = Annotated[ApiClient, Depends(require_role("reviewer"))]
Curator = Annotated[ApiClient, Depends(require_role("curator"))]


@router.get("", response_model=EpistemicLexiconPage)
async def list_epistemic_lexicon_entries(
    session: DatabaseSession,
    _reviewer: Reviewer,
    status: str | None = Query(
        default=None,
        pattern="^(pending|active|needs_review|policy_conflict_hold|rejected|superseded)$",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> EpistemicLexiconPage:
    statement = select(EpistemicLexiconEntry)
    count_statement = select(func.count(EpistemicLexiconEntry.id))
    if status is not None:
        statement = statement.where(EpistemicLexiconEntry.status == status)
        count_statement = count_statement.where(EpistemicLexiconEntry.status == status)
    entries = list(
        await session.scalars(
            statement.order_by(EpistemicLexiconEntry.updated_at.desc(), EpistemicLexiconEntry.id)
            .offset(offset)
            .limit(limit)
        )
    )
    grouped = await session.execute(
        select(EpistemicLexiconEntry.status, func.count(EpistemicLexiconEntry.id)).group_by(
            EpistemicLexiconEntry.status
        )
    )
    grouped_jobs = await session.execute(
        select(Job.status, func.count(Job.id))
        .where(Job.type == EPISTEMIC_ENRICHMENT_JOB_TYPE)
        .group_by(Job.status)
    )
    distinct_keys = (
        select(
            EpistemicLexiconEntry.lemma,
            EpistemicLexiconEntry.pos,
            EpistemicLexiconEntry.construction_family,
        )
        .distinct()
        .subquery()
    )
    total_keys = int(await session.scalar(select(func.count()).select_from(distinct_keys)) or 0)
    active_entries = int(
        await session.scalar(
            select(func.count(EpistemicLexiconEntry.id)).where(
                EpistemicLexiconEntry.status == "active"
            )
        )
        or 0
    )
    failed_jobs = int(
        await session.scalar(
            select(func.count(Job.id)).where(
                Job.type == EPISTEMIC_ENRICHMENT_JOB_TYPE, Job.status == "failed"
            )
        )
        or 0
    )
    disagreement_entries = int(
        await session.scalar(
            select(func.count(EpistemicLexiconEntry.id)).where(
                EpistemicLexiconEntry.status == "needs_review",
                EpistemicLexiconEntry.review_reason == "tier_disagreement",
            )
        )
        or 0
    )
    fallback_candidates = int(
        await session.scalar(
            select(func.count(Candidate.id)).where(
                Candidate.occurrences.contains(
                    [{"epistemic_provenance": "syntax_gate_oov_default"}]
                )
            )
        )
        or 0
    )
    return EpistemicLexiconPage(
        items=[EpistemicLexiconEntryRead.model_validate(entry) for entry in entries],
        total=int(await session.scalar(count_statement) or 0),
        counts={key: value for key, value in grouped},
        jobs_by_status={key: value for key, value in grouped_jobs},
        failed_enrichment_jobs=failed_jobs,
        prompt_disagreement_entries=disagreement_entries,
        fallback_candidate_count=fallback_candidates,
        active_coverage=active_entries / total_keys if total_keys else 0.0,
    )


@router.get("/{entry_id}/audit", response_model=list[EpistemicLexiconAuditRead])
async def get_epistemic_lexicon_audit(
    entry_id: UUID, session: DatabaseSession, _reviewer: Reviewer
) -> list[EpistemicLexiconAuditRead]:
    rows = list(
        await session.scalars(
            select(EpistemicLexiconAudit)
            .where(EpistemicLexiconAudit.entry_id == entry_id)
            .order_by(EpistemicLexiconAudit.created_at, EpistemicLexiconAudit.id)
        )
    )
    return [EpistemicLexiconAuditRead.model_validate(row) for row in rows]


@router.post("/{entry_id}/review", response_model=EpistemicLexiconEntryRead)
async def review_epistemic_lexicon_entry(
    entry_id: UUID,
    payload: EpistemicLexiconReview,
    session: DatabaseSession,
    curator: Curator,
) -> EpistemicLexiconEntryRead:
    try:
        entry = await review_epistemic_entry(
            session,
            entry_id=entry_id,
            actor_id=curator.id,
            action=payload.action,
        )
    except ValueError as error:
        status_code = 409 if "Locked neutral policy" in str(error) else 404
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    await session.commit()
    return EpistemicLexiconEntryRead.model_validate(entry)
