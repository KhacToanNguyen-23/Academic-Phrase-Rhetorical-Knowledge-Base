"""Published taxonomy and release endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.taxonomy import service
from aprkb.modules.taxonomy.schemas import ReleaseSummary, TaxonomyTree

router = APIRouter(tags=["taxonomy"])
admin_router = APIRouter(tags=["admin releases"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Client = Annotated[ApiClient, Depends(require_role("client"))]
Admin = Annotated[ApiClient, Depends(require_role("admin"))]


@router.get("", response_model=TaxonomyTree)
async def get_taxonomy(_client: Client, session: DatabaseSession) -> TaxonomyTree:
    tree = await service.get_published_tree(session)
    if tree is None:
        raise HTTPException(status_code=404, detail="No published taxonomy release")
    return TaxonomyTree.model_validate(tree)


@router.get("/releases", response_model=list[ReleaseSummary])
async def get_releases(_client: Client, session: DatabaseSession) -> list[ReleaseSummary]:
    return [ReleaseSummary.model_validate(item) for item in await service.get_releases(session)]


@admin_router.post("/releases/{release_id}/publish", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def publish_release(release_id: UUID, request: Request, _actor: Admin) -> None:
    del release_id, request
    raise HTTPException(status_code=501, detail="Taxonomy publishing is not implemented")
