"""Reviewer queue and two-round decision endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.models import Candidate
from aprkb.modules.mining.schemas import SlotDefinition, is_safe_masked_frame
from aprkb.modules.review import service
from aprkb.modules.review.schemas import (
    CandidateIntentUpdate,
    CandidateSummary,
    ReviewDecisionCreate,
    ReviewDecisionResult,
)
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import is_safe_construction_frame

router = APIRouter(tags=["candidate review"])
_POLICIES = load_policy_bundle()
_REPORTING_FORMS = _POLICIES.reporting_verbs.all_forms
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Reviewer = Annotated[ApiClient, Depends(require_role("reviewer"))]


@router.get("/review-queue", response_model=list[CandidateSummary])
async def list_queue(_reviewer: Reviewer, session: DatabaseSession) -> list[CandidateSummary]:
    return [_safe_summary(candidate) for candidate in await service.list_review_queue(session)]


def _safe_summary(candidate: Candidate) -> CandidateSummary:
    if not isinstance(candidate.slots, dict):
        raise HTTPException(status_code=409, detail="Candidate slot schema is invalid")
    try:
        slots = {
            name: SlotDefinition.model_validate(value) for name, value in candidate.slots.items()
        }
    except (TypeError, ValueError, ValidationError):
        raise HTTPException(status_code=409, detail="Candidate slot schema is invalid") from None
    if set(slots) - {"X", "Y", "Z"}:
        raise HTTPException(status_code=409, detail="Candidate slot names are invalid")
    if not (
        is_safe_masked_frame(candidate.canonical_frame, _REPORTING_FORMS)
        or is_safe_construction_frame(candidate.canonical_frame, _POLICIES.constructions)
    ):
        raise HTTPException(status_code=409, detail="Candidate frame is not safely abstracted")
    return CandidateSummary(
        id=candidate.id,
        canonical_frame=candidate.canonical_frame,
        slots=slots,
        intent_id=candidate.intent_id,
        confidence=candidate.confidence,
        epistemic_strength=candidate.epistemic_strength,
        source_sentence_ids=candidate.source_sentence_ids,
        status=candidate.status,
    )


@router.put("/review-queue/{candidate_id}/intent", response_model=CandidateSummary)
async def assign_intent(
    candidate_id: UUID,
    payload: CandidateIntentUpdate,
    request: Request,
    reviewer: Reviewer,
    session: DatabaseSession,
) -> CandidateSummary:
    candidate = await service.assign_intent(
        session,
        candidate_id=candidate_id,
        payload=payload,
        reviewer=reviewer,
        request_id=request.state.request_id,
    )
    return _safe_summary(candidate)


@router.post("/review-queue/{candidate_id}/decisions", response_model=ReviewDecisionResult)
async def decide_candidate(
    candidate_id: UUID,
    payload: ReviewDecisionCreate,
    request: Request,
    reviewer: Reviewer,
    session: DatabaseSession,
) -> ReviewDecisionResult:
    result = await service.decide(
        session,
        candidate_id=candidate_id,
        payload=payload,
        reviewer=reviewer,
        request_id=request.state.request_id,
    )
    return ReviewDecisionResult.model_validate(result)
