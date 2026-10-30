"""Reviewer queue and two-round decision endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.review import service
from aprkb.modules.review.schemas import (
    CandidateSummary,
    ReviewDecisionCreate,
    ReviewDecisionResult,
)

router = APIRouter(tags=["candidate review"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Reviewer = Annotated[ApiClient, Depends(require_role("reviewer"))]


@router.get("/review-queue", response_model=list[CandidateSummary])
async def list_queue(_reviewer: Reviewer, session: DatabaseSession) -> list[CandidateSummary]:
    return [
        CandidateSummary.model_validate(candidate)
        for candidate in await service.list_review_queue(session)
    ]


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
