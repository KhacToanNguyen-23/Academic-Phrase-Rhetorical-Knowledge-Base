"""Admin corpus upload, mining enqueue and worker-job status endpoints."""

from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.config import settings
from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.corpus.blobstore import LocalBlobStore
from aprkb.modules.corpus.schemas import ArticleImportCreate
from aprkb.modules.corpus.service import (
    create_upload,
    enqueue_import,
    enqueue_mining,
    get_license,
)
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.models import Job

admin_router = APIRouter(tags=["admin corpus and jobs"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Curator = Annotated[ApiClient, Depends(require_role("curator"))]
_ALLOWED_SUFFIXES = {".txt", ".md", ".markdown", ".xml", ".jats", ".pdf"}


@admin_router.post("/corpus/articles", status_code=status.HTTP_202_ACCEPTED)
async def upload_article(
    request: Request,
    session: DatabaseSession,
    actor: Curator,
    file: Annotated[UploadFile, File()],
    license_code: Annotated[str, Form()],
    title: Annotated[str | None, Form()] = None,
) -> dict[str, str]:
    suffix = Path(file.filename or "").suffix.casefold()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415, detail="Supported formats are TXT, Markdown, XML/JATS, and PDF"
        )
    license_row = await get_license(session, license_code)
    content = await file.read()
    article_id = uuid4()
    blob_key = f"articles/{article_id.hex}{suffix}"
    blob_store = LocalBlobStore(settings.blob_dir)
    blob_store.put(blob_key, content)
    try:
        article, job = await create_upload(
            session,
            article_id=article_id,
            title=title,
            license_row=license_row,
            blob_key=blob_key,
            actor=actor,
            request_id=request.state.request_id,
        )
    except BaseException:
        blob_store.delete(blob_key)
        raise
    return {"article_id": str(article.id), "job_id": str(job.id), "status": job.status}


@admin_router.post("/corpus/imports", status_code=status.HTTP_202_ACCEPTED)
async def import_articles(
    payload: ArticleImportCreate,
    request: Request,
    session: DatabaseSession,
    actor: Curator,
) -> dict[str, str]:
    job = await enqueue_import(
        session,
        source_name=settings.article_source,
        cursor=payload.cursor,
        limit=payload.limit or settings.article_import_batch_limit,
        actor=actor,
        request_id=request.state.request_id,
    )
    return {"job_id": str(job.id), "status": job.status}


@admin_router.post("/corpus/articles/{article_id}/mine", status_code=status.HTTP_202_ACCEPTED)
async def mine_article(
    article_id: UUID,
    request: Request,
    session: DatabaseSession,
    actor: Curator,
) -> dict[str, str]:
    job = await enqueue_mining(
        session,
        article_id=article_id,
        actor=actor,
        request_id=request.state.request_id,
    )
    return {"job_id": str(job.id), "status": job.status}


@admin_router.get("/jobs/{job_id}")
async def get_job(job_id: UUID, _actor: Curator, session: DatabaseSession) -> dict[str, object]:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "attempts": job.attempts,
        "error": job.error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
