"""Admin endpoints for the phrase extraction page."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.extraction import repository, service
from aprkb.modules.extraction.schemas import (
    ArticleRowRead,
    ArticleTextRead,
    BatchRead,
    BulkDecisionCreate,
    BulkDecisionResult,
    MineRequest,
    MineResult,
    PhraseDecisionCreate,
    PhraseDecisionResult,
    PhrasePage,
    PhraseStatus,
)
from aprkb.modules.identity.models import ApiClient

admin_router = APIRouter(tags=["extraction"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Reviewer = Annotated[ApiClient, Depends(require_role("reviewer"))]
Curator = Annotated[ApiClient, Depends(require_role("curator"))]
ArticleIds = Annotated[list[UUID] | None, Query(alias="article_id")]
BatchIds = Annotated[list[UUID] | None, Query(alias="batch_id")]


@admin_router.get("/corpus/batches", response_model=list[BatchRead])
async def list_batches(_actor: Reviewer, session: DatabaseSession) -> list[BatchRead]:
    return [BatchRead.model_validate(row) for row in await repository.list_batches(session)]


@admin_router.get("/corpus/articles", response_model=list[ArticleRowRead])
async def list_articles(
    _actor: Reviewer,
    session: DatabaseSession,
    batch_id: BatchIds = None,
    unbatched: bool = False,
) -> list[ArticleRowRead]:
    scope = repository.article_scope(article_ids=[], batch_ids=batch_id or [], unbatched=unbatched)
    rows = await repository.list_articles(session, scope)
    return [ArticleRowRead.model_validate(row) for row in rows]


@admin_router.get("/corpus/articles/{article_id}/text", response_model=ArticleTextRead)
async def article_text(
    article_id: UUID, _actor: Reviewer, session: DatabaseSession
) -> ArticleTextRead:
    return await service.article_text(session, article_id)


@admin_router.post("/corpus/mine", response_model=MineResult, status_code=status.HTTP_202_ACCEPTED)
async def mine(
    payload: MineRequest, request: Request, actor: Curator, session: DatabaseSession
) -> MineResult:
    return await service.mine_scope(
        session, payload=payload, actor=actor, request_id=request.state.request_id
    )


@admin_router.get("/extraction/phrases", response_model=PhrasePage)
async def list_phrases(
    _actor: Reviewer,
    session: DatabaseSession,
    status_filter: Annotated[PhraseStatus, Query(alias="status")] = "pending",
    article_id: ArticleIds = None,
    batch_id: BatchIds = None,
    unbatched: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PhrasePage:
    scope = repository.article_scope(
        article_ids=article_id or [], batch_ids=batch_id or [], unbatched=unbatched
    )
    return await service.list_phrases(
        session, status=status_filter, scope=scope, limit=limit, offset=offset
    )


@admin_router.post("/extraction/phrases/decisions", response_model=BulkDecisionResult)
async def decide_many(
    payload: BulkDecisionCreate, request: Request, reviewer: Reviewer, session: DatabaseSession
) -> BulkDecisionResult:
    return await service.decide_many(
        session, payload=payload, reviewer=reviewer, request_id=request.state.request_id
    )


@admin_router.post(
    "/extraction/phrases/{candidate_id}/decision", response_model=PhraseDecisionResult
)
async def decide_phrase(
    candidate_id: UUID,
    payload: PhraseDecisionCreate,
    request: Request,
    reviewer: Reviewer,
    session: DatabaseSession,
) -> PhraseDecisionResult:
    return await service.decide_phrase(
        session,
        candidate_id=candidate_id,
        payload=payload,
        reviewer=reviewer,
        request_id=request.state.request_id,
    )
