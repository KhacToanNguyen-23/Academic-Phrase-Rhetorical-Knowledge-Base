"""Admin corpus upload, mining enqueue and worker-job status endpoints."""

from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.config import settings
from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.corpus.blobstore import LocalBlobStore
from aprkb.modules.corpus.dedup import (
    find_content_duplicate,
    find_metadata_duplicate,
    lock_corpus_writes,
)
from aprkb.modules.corpus.identity import content_hash
from aprkb.modules.corpus.schemas import (
    ArticleImportCreate,
    ImportProfileCreate,
    ImportProfileRead,
    ImportProfileUpdate,
    JobAlertAcknowledge,
    JobAlertRead,
    JobAttemptRead,
    JobRead,
    JobRetryRequest,
    SlrTaxonomyPage,
)
from aprkb.modules.corpus.service import (
    create_import_profile,
    create_upload,
    enqueue_import,
    enqueue_mining,
    get_import_profile,
    get_license,
    list_import_profiles,
    update_import_profile,
)
from aprkb.modules.corpus.sources import build_article_source
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.models import Job, JobAlert, JobAttempt
from aprkb.modules.mining.operations import acknowledge_alert, retry_manually

admin_router = APIRouter(tags=["admin corpus and jobs"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Curator = Annotated[ApiClient, Depends(require_role("curator"))]
_ALLOWED_SUFFIXES = {".txt", ".md", ".markdown", ".xml", ".jats", ".pdf"}


@admin_router.get("/corpus/import-profiles", response_model=list[ImportProfileRead])
async def import_profile_list(_actor: Curator, session: DatabaseSession) -> list[ImportProfileRead]:
    return [
        ImportProfileRead.model_validate(profile) for profile in await list_import_profiles(session)
    ]


@admin_router.post("/corpus/import-profiles", response_model=ImportProfileRead, status_code=201)
async def import_profile_create(
    payload: ImportProfileCreate, request: Request, session: DatabaseSession, actor: Curator
) -> ImportProfileRead:
    profile = await create_import_profile(session, payload, actor, request.state.request_id)
    return ImportProfileRead.model_validate(profile)


@admin_router.get("/corpus/import-profiles/{profile_id}", response_model=ImportProfileRead)
async def import_profile_get(
    profile_id: UUID, _actor: Curator, session: DatabaseSession
) -> ImportProfileRead:
    return ImportProfileRead.model_validate(await get_import_profile(session, profile_id))


@admin_router.patch("/corpus/import-profiles/{profile_id}", response_model=ImportProfileRead)
async def import_profile_update(
    profile_id: UUID,
    payload: ImportProfileUpdate,
    request: Request,
    session: DatabaseSession,
    actor: Curator,
) -> ImportProfileRead:
    profile = await update_import_profile(
        session, profile_id, payload, actor, request.state.request_id
    )
    return ImportProfileRead.model_validate(profile)


@admin_router.post("/corpus/articles", status_code=status.HTTP_202_ACCEPTED)
async def upload_article(
    request: Request,
    session: DatabaseSession,
    actor: Curator,
    file: Annotated[UploadFile, File()],
    license_code: Annotated[str, Form()],
    title: Annotated[str | None, Form()] = None,
    doi: Annotated[str | None, Form()] = None,
) -> dict[str, str]:
    suffix = Path(file.filename or "").suffix.casefold()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415, detail="Supported formats are TXT, Markdown, XML/JATS, and PDF"
        )
    license_row = await get_license(session, license_code)
    content = await file.read()
    blob_store = LocalBlobStore(settings.blob_dir)
    await lock_corpus_writes(session)
    match = await find_metadata_duplicate(session, source="upload", external_id=None, doi=doi)
    digest = content_hash(content)
    if match is None:
        match = await find_content_duplicate(session, digest, blob_store)
    if match is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_article",
                **match.detail(external_id=None, title=title),
            },
        )
    article_id = uuid4()
    blob_key = f"articles/{article_id.hex}{suffix}"
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
            doi=doi,
            content_sha256=digest,
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
    profile = await get_import_profile(session, payload.profile_id) if payload.profile_id else None
    if profile is not None and not profile.is_active:
        raise HTTPException(status_code=409, detail="Import profile is inactive")
    if profile is not None and settings.article_source == "null":
        raise HTTPException(status_code=409, detail="No article source is configured")
    job = await enqueue_import(
        session,
        source_name=settings.article_source,
        cursor=payload.cursor,
        limit=profile.batch_limit
        if profile
        else (payload.limit or settings.article_import_batch_limit),
        actor=actor,
        request_id=request.state.request_id,
        profile=profile,
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


@admin_router.get("/jobs/{job_id}", response_model=JobRead)
async def get_job(job_id: UUID, _actor: Curator, session: DatabaseSession) -> JobRead:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_read(job)


def _job_read(job: Job) -> JobRead:
    return JobRead.model_validate(job).model_copy(
        update={
            "manual_retry_limit": settings.job_manual_retry_limit,
        }
    )


@admin_router.get("/jobs", response_model=list[JobRead])
async def list_jobs(
    _actor: Curator,
    session: DatabaseSession,
    status: Literal["queued", "processing", "succeeded", "failed"] | None = None,
    job_type: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[JobRead]:
    query = select(Job).order_by(Job.created_at.desc(), Job.id.desc()).limit(limit).offset(offset)
    if status is not None:
        query = query.where(Job.status == status)
    if job_type is not None:
        query = query.where(Job.type == job_type)
    return [_job_read(job) for job in await session.scalars(query)]


@admin_router.get("/jobs/{job_id}/attempts", response_model=list[JobAttemptRead])
async def job_attempt_history(
    job_id: UUID,
    _actor: Curator,
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[JobAttemptRead]:
    if await session.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    rows = await session.scalars(
        select(JobAttempt)
        .where(JobAttempt.job_id == job_id)
        .order_by(JobAttempt.attempt_no.desc())
        .limit(limit)
        .offset(offset)
    )
    return [JobAttemptRead.model_validate(row) for row in rows]


@admin_router.post("/jobs/{job_id}/retry", response_model=JobRead)
async def manual_job_retry(
    job_id: UUID,
    payload: JobRetryRequest,
    request: Request,
    session: DatabaseSession,
    actor: Curator,
) -> JobRead:
    return _job_read(
        await retry_manually(
            session,
            job_id=job_id,
            expected_attempts=payload.expected_attempts,
            rationale=payload.rationale,
            actor=actor,
            request_id=request.state.request_id,
        )
    )


@admin_router.get("/job-alerts", response_model=list[JobAlertRead])
async def list_job_alerts(
    _actor: Curator,
    session: DatabaseSession,
    active_only: bool = True,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[JobAlertRead]:
    query = select(JobAlert).order_by(JobAlert.last_failed_at.desc(), JobAlert.id.desc())
    if active_only:
        query = query.where(JobAlert.active.is_(True))
    rows = await session.scalars(query.limit(limit).offset(offset))
    return [JobAlertRead.model_validate(row) for row in rows]


@admin_router.post("/job-alerts/{alert_id}/acknowledge", response_model=JobAlertRead)
async def acknowledge_job_alert(
    alert_id: UUID,
    payload: JobAlertAcknowledge,
    request: Request,
    session: DatabaseSession,
    actor: Curator,
) -> JobAlertRead:
    return JobAlertRead.model_validate(
        await acknowledge_alert(
            session,
            alert_id=alert_id,
            expected_last_failed_at=payload.expected_last_failed_at,
            actor=actor,
            request_id=request.state.request_id,
        )
    )


@admin_router.get("/corpus/sources/slr/taxonomy", response_model=SlrTaxonomyPage)
async def slr_taxonomy(
    _actor: Curator,
    level: str = Query(pattern="^(domain|field|subfield|topic)$"),
    parentId: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=100),
) -> dict[str, object]:
    if settings.article_source != "slr":
        raise HTTPException(status_code=409, detail="SLR article source is not configured")
    try:
        source = build_article_source("slr")
        try:
            data = await source.get_taxonomy(level, parentId, cursor, limit)
        finally:
            await source.aclose()
        return data
    except Exception as error:
        raise HTTPException(status_code=502, detail="SLR taxonomy request failed") from error
