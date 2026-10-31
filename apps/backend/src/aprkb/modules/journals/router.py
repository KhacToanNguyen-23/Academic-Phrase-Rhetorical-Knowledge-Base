"""Journal reads and curator-managed guideline rules."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.journals import service
from aprkb.modules.journals.schemas import GuidelineCreate, GuidelineRead, JournalRead

router = APIRouter(tags=["journals"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Client = Annotated[ApiClient, Depends(require_role("client"))]
Curator = Annotated[ApiClient, Depends(require_role("curator"))]


@router.get("", response_model=list[JournalRead])
async def list_journals(_client: Client, session: DatabaseSession) -> list[JournalRead]:
    return [JournalRead.model_validate(item) for item in await service.list_journals(session)]


@router.get("/{journal_id}", response_model=JournalRead)
async def get_journal(journal_id: UUID, _client: Client, session: DatabaseSession) -> JournalRead:
    return JournalRead.model_validate(await service.get_journal(session, journal_id))


@router.post(
    "/{journal_id}/guidelines",
    response_model=GuidelineRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_guideline(
    journal_id: UUID,
    payload: GuidelineCreate,
    request: Request,
    actor: Curator,
    session: DatabaseSession,
) -> GuidelineRead:
    rule = await service.create_guideline(
        session,
        journal_id=journal_id,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return GuidelineRead.model_validate(rule)
