"""Admin route for explicitly queueing proposal-only frame labels."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.label_review_schemas import (
    BulkFrameLabelReviewCreate,
    BulkFrameLabelReviewResult,
    FrameLabelReviewPage,
)
from aprkb.modules.mining.label_review_service import decide_frame_labels, list_frame_label_reviews
from aprkb.modules.mining.labeling_service import enqueue_frame_label_job

router = APIRouter(prefix="/admin/mining/frames", tags=["frame labels"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Curator = Annotated[ApiClient, Depends(require_role("curator"))]
Reviewer = Annotated[ApiClient, Depends(require_role("reviewer"))]


class FrameLabelJobQueued(BaseModel):
    job_id: UUID
    status: str


@router.post("/label", response_model=FrameLabelJobQueued, status_code=202)
async def queue_frame_label_job(
    request: Request,
    session: DatabaseSession,
    actor: Curator,
) -> FrameLabelJobQueued:
    job = await enqueue_frame_label_job(
        session,
        actor=actor,
        request_id=request.state.request_id,
    )
    return FrameLabelJobQueued(job_id=job.id, status=job.status)


@router.get("", response_model=FrameLabelReviewPage)
async def get_frame_label_reviews(
    session: DatabaseSession,
    _reviewer: Reviewer,
    label_code: str | None = None,
    min_confidence: float | None = Query(default=None, ge=0, le=1),
    needs_attention: bool | None = None,
    agreement: str | None = None,
    paper_count: int | None = Query(default=None, ge=0),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> FrameLabelReviewPage:
    return await list_frame_label_reviews(
        session,
        label_code=label_code,
        min_confidence=min_confidence,
        needs_attention=needs_attention,
        agreement=agreement,
        paper_count=paper_count,
        offset=offset,
        limit=limit,
    )


@router.post("/decisions", response_model=BulkFrameLabelReviewResult)
async def post_frame_label_decisions(
    payload: BulkFrameLabelReviewCreate,
    request: Request,
    session: DatabaseSession,
    reviewer: Reviewer,
) -> BulkFrameLabelReviewResult:
    return await decide_frame_labels(
        session,
        payload=payload,
        reviewer=reviewer,
        request_id=request.state.request_id,
    )
