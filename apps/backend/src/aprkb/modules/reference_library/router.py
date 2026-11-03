"""Read-only public routes for internal reference browsing."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_current_client, get_db_session
from aprkb.modules.reference_library import service
from aprkb.modules.reference_library.schemas import (
    CategoryDetailResponse,
    CategoryListResponse,
    SearchResponse,
)


async def require_enabled(request: Request) -> None:
    if not request.app.state.settings.reference_library_enabled:
        raise HTTPException(status_code=404, detail="Reference library is disabled")


router = APIRouter(
    tags=["reference library"],
    dependencies=[Depends(require_enabled), Depends(get_current_client)],
)
Session = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(session: Session) -> CategoryListResponse:
    return await service.list_categories(session)


@router.get("/categories/{slug}", response_model=CategoryDetailResponse)
async def get_category(slug: str, session: Session) -> CategoryDetailResponse:
    return await service.get_category(session, slug)


@router.get("/search", response_model=SearchResponse)
async def search(
    session: Session,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    category: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchResponse:
    return await service.search_entries(session, q, category, limit)
