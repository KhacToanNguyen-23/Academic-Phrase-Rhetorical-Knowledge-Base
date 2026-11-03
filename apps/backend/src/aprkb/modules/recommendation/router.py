"""Client recommendation endpoint over the pure ranking pipeline."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.recommendation import service
from aprkb.modules.recommendation.schemas import RecommendationRequest, RecommendationResponse

router = APIRouter(tags=["recommendations"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Client = Annotated[ApiClient, Depends(require_role("client"))]


@router.post("", response_model=RecommendationResponse)
async def create_recommendation(
    payload: RecommendationRequest,
    request: Request,
    actor: Client,
    session: DatabaseSession,
) -> RecommendationResponse:
    """FR-07.1–.4: expose context search, gated ranking and fallback to authenticated Writers."""
    result = await service.recommend(
        session,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
        policy_bundle=request.app.state.policy_bundle,
    )
    return RecommendationResponse.model_validate(result)
