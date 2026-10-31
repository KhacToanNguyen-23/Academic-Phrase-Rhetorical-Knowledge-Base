"""Client feedback and validation override endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.analytics import service
from aprkb.modules.analytics.schemas import CreatedRecord, FeedbackCreate, OverrideCreate
from aprkb.modules.identity.models import ApiClient

router = APIRouter(tags=["feedback"])
override_router = APIRouter(tags=["overrides"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Client = Annotated[ApiClient, Depends(require_role("client"))]


@router.post("", response_model=CreatedRecord, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreate,
    request: Request,
    actor: Client,
    session: DatabaseSession,
) -> CreatedRecord:
    row = await service.create_feedback(
        session, payload=payload, actor=actor, request_id=request.state.request_id
    )
    return CreatedRecord(id=row.id)


@override_router.post("", response_model=CreatedRecord, status_code=status.HTTP_201_CREATED)
async def create_override(
    payload: OverrideCreate,
    request: Request,
    actor: Client,
    session: DatabaseSession,
) -> CreatedRecord:
    row = await service.create_override(
        session, payload=payload, actor=actor, request_id=request.state.request_id
    )
    return CreatedRecord(id=row.id)
