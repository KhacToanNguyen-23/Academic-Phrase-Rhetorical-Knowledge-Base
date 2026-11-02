"""Admin endpoints for creating text-free gold sample batches."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.gold.schemas import (
    GoldItemDetail,
    GoldItemSummary,
    GoldLabelJobResult,
    GoldReviewDecision,
    GoldReviewResult,
    GoldSampleCreate,
    GoldSampleResult,
    GoldStats,
)
from aprkb.modules.gold.service import (
    create_sample,
    enqueue_label_job,
    get_gold_item,
    get_gold_stats,
    list_gold_items,
    review_gold_item,
)
from aprkb.modules.identity.models import ApiClient

router = APIRouter(prefix="/admin/gold", tags=["admin gold"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Curator = Annotated[ApiClient, Depends(require_role("curator"))]
Reviewer = Annotated[ApiClient, Depends(require_role("reviewer"))]


@router.post("/samples", response_model=GoldSampleResult, status_code=202)
async def create_gold_sample(
    payload: GoldSampleCreate,
    request: Request,
    session: DatabaseSession,
    actor: Curator,
) -> GoldSampleResult:
    return await create_sample(
        session, payload=payload, actor=actor, request_id=request.state.request_id
    )


@router.post("/samples/{sample_batch}/label", response_model=GoldLabelJobResult, status_code=202)
async def label_gold_sample(
    sample_batch: str,
    request: Request,
    session: DatabaseSession,
    actor: Curator,
) -> GoldLabelJobResult:
    try:
        job = await enqueue_label_job(
            session,
            sample_batch=sample_batch,
            actor=actor,
            request_id=request.state.request_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Sample batch has no pending labels") from error
    return GoldLabelJobResult(job_id=job.id, sample_batch=sample_batch)


@router.get("/items", response_model=list[GoldItemSummary])
async def get_gold_items(
    session: DatabaseSession,
    _actor: Reviewer,
    status: str | None = None,
    split: str | None = None,
    section: str | None = None,
    sample_batch: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[GoldItemSummary]:
    return await list_gold_items(
        session,
        status=status,
        split=split,
        section=section,
        sample_batch=sample_batch,
        offset=offset,
        limit=limit,
    )


@router.get("/stats", response_model=GoldStats)
async def get_gold_item_stats(session: DatabaseSession, _actor: Reviewer) -> GoldStats:
    return await get_gold_stats(session)


@router.get("/items/{item_id}", response_model=GoldItemDetail)
async def get_gold_item_detail(
    item_id: UUID,
    request: Request,
    session: DatabaseSession,
    _actor: Reviewer,
) -> GoldItemDetail:
    return await get_gold_item(session, item_id=item_id, request_id=request.state.request_id)


@router.post("/items/{item_id}/review", response_model=GoldReviewResult)
async def decide_gold_item(
    item_id: UUID,
    payload: GoldReviewDecision,
    request: Request,
    session: DatabaseSession,
    actor: Reviewer,
) -> GoldReviewResult:
    return await review_gold_item(
        session,
        item_id=item_id,
        payload=payload,
        reviewer=actor,
        request_id=request.state.request_id,
    )
