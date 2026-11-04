"""Admin import and import-history routes for the Academic Vocabulary List."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.vocabulary.schemas import ImportResult, ImportRunPage
from aprkb.modules.vocabulary.service import import_workbook, list_import_history

admin_router = APIRouter(tags=["vocabulary"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Curator = Annotated[ApiClient, Depends(require_role("curator"))]


@admin_router.post("/vocabulary/imports", response_model=ImportResult)
async def vocabulary_import(
    request: Request,
    session: DatabaseSession,
    actor: Curator,
    file: Annotated[UploadFile, File()],
) -> ImportResult:
    if Path(file.filename or "").suffix.casefold() != ".xlsx":
        raise HTTPException(status_code=415, detail="Only .xlsx files are supported")
    policy = request.app.state.policy_bundle.vocabulary_import
    content = await file.read(policy.max_upload_bytes + 1)
    if len(content) > policy.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File is too large")
    return await import_workbook(
        session,
        content=content,
        filename=file.filename or "upload.xlsx",
        actor=actor,
        request_id=request.state.request_id,
        policy=policy,
    )


@admin_router.get("/vocabulary/imports", response_model=ImportRunPage)
async def vocabulary_import_list(
    _actor: Curator,
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ImportRunPage:
    return await list_import_history(session, limit=limit, offset=offset)
