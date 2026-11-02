"""Authenticated render endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.composition import service
from aprkb.modules.composition.schemas import RenderRequest, RenderResponse
from aprkb.modules.identity.models import ApiClient

router = APIRouter(tags=["composition"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Client = Annotated[ApiClient, Depends(require_role("client"))]


@router.post("", response_model=RenderResponse)
async def render(
    payload: RenderRequest, client: Client, session: DatabaseSession
) -> RenderResponse:
    """FR-07.5: render only the selected candidate/version issued to the authenticated client."""
    result = await service.render_pattern(
        session,
        recommendation_id=payload.recommendation_id,
        pattern_version_id=payload.pattern_version_id,
        client_id=client.id,
        slots=payload.slots,
    )
    return RenderResponse.model_validate(result)
