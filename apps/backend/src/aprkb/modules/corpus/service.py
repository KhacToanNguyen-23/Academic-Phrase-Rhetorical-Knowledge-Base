"""Persistence operations for article upload and mining enqueue requests."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.logging import get_logger
from aprkb.modules.audit.service import record_event
from aprkb.modules.corpus.importer import IMPORT_JOB_TYPE
from aprkb.modules.corpus.models import Article, ImportProfile, License
from aprkb.modules.corpus.parsers.pdf_parser import PARSER_VERSION, PdfInspection
from aprkb.modules.corpus.pdf_schemas import PdfMetadata
from aprkb.modules.corpus.schemas import ImportProfileCreate, ImportProfileUpdate
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.models import Job

logger = get_logger(__name__)


async def get_license(session: AsyncSession, license_code: str) -> License:
    license_row = await session.scalar(select(License).where(License.code == license_code))
    if license_row is None:
        raise HTTPException(status_code=422, detail="Unknown license_code")
    return license_row


async def create_upload(
    session: AsyncSession,
    *,
    article_id: UUID,
    title: str | None,
    license_row: License,
    blob_key: str,
    actor: ApiClient,
    request_id: str,
    doi: str | None = None,
    content_sha256: str | None = None,
    pdf: PdfInspection | None = None,
    metadata: PdfMetadata | None = None,
) -> tuple[Article, Job]:
    article = Article(
        id=article_id,
        source="upload",
        title=title,
        doi=doi,
        content_sha256=content_sha256,
        license_id=license_row.id,
        blob_key=blob_key,
        ingest_status="pending",
        created_by=actor.id,
    )
    if pdf is not None and metadata is not None:
        article.pdf_text_sha256 = pdf.text_sha256
        article.page_count = pdf.page_count
        article.parser_version = PARSER_VERSION
        article.authors = metadata.authors
        article.publication_year = metadata.publication_year
        article.journal_id = metadata.journal_id
        article.genre_id = metadata.genre_id
        article.source_url = str(metadata.source_url) if metadata.source_url else None
        article.metadata_provenance = {
            "reviewed_by": str(actor.id),
            "reviewed_at": datetime.now(UTC).isoformat(),
            "license_code": license_row.code,
            "method": "pdf-properties-and-first-page-v1",
            "suggestions": {
                "title": pdf.title,
                "authors": list(pdf.authors),
                "doi_candidates": list(pdf.doi_candidates),
            },
            "confirmed_fields": metadata.model_dump(mode="json"),
        }
    job = Job(
        type="ingest_article",
        payload={"article_id": str(article_id)},
        status="queued",
        created_by=actor.id,
    )
    session.add_all([article, job])
    await session.flush()
    await record_event(
        session,
        actor_id=actor.id,
        action="corpus.article.upload",
        entity_type="article",
        entity_id=article.id,
        after={"title": title, "license_code": license_row.code, "job_id": str(job.id)},
        request_id=request_id,
    )
    await session.commit()
    logger.info(
        "Article uploaded article_id=%s license=%s ingest_job_id=%s actor_id=%s request_id=%s",
        article.id,
        license_row.code,
        job.id,
        actor.id,
        request_id,
    )
    return article, job


async def enqueue_import(
    session: AsyncSession,
    *,
    source_name: str,
    cursor: str | None,
    limit: int,
    actor: ApiClient,
    request_id: str,
    profile: ImportProfile | None = None,
) -> Job:
    if source_name == "null":
        logger.warning("Import rejected: no article source configured request_id=%s", request_id)
        raise HTTPException(status_code=409, detail="No article source is configured")
    job = Job(
        type=IMPORT_JOB_TYPE,
        payload={
            "source": source_name,
            "cursor": cursor,
            "limit": limit,
            **(
                {
                    "profile_id": str(profile.id),
                    "filters": profile.filters,
                    "artifact_kinds": profile.artifact_kinds,
                }
                if profile
                else {}
            ),
        },
        status="queued",
        created_by=actor.id,
    )
    session.add(job)
    await session.flush()
    await record_event(
        session,
        actor_id=actor.id,
        action="corpus.import.enqueue",
        entity_type="job",
        entity_id=job.id,
        after={
            "source": source_name,
            "cursor": cursor,
            "limit": limit,
            **({"profile_id": str(profile.id)} if profile else {}),
        },
        request_id=request_id,
    )
    await session.commit()
    logger.info(
        "Import job queued job_id=%s source=%s profile_id=%s limit=%s cursor=%s actor_id=%s "
        "request_id=%s",
        job.id,
        source_name,
        profile.id if profile else None,
        limit,
        "yes" if cursor else "no",
        actor.id,
        request_id,
    )
    return job


async def list_import_profiles(session: AsyncSession) -> list[ImportProfile]:
    return list(await session.scalars(select(ImportProfile).order_by(ImportProfile.name)))


async def get_import_profile(session: AsyncSession, profile_id: UUID) -> ImportProfile:
    profile = await session.get(ImportProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Import profile not found")
    return profile


async def create_import_profile(
    session: AsyncSession, payload: ImportProfileCreate, actor: ApiClient, request_id: str
) -> ImportProfile:
    profile = ImportProfile(
        name=payload.name,
        source=payload.source,
        filters=payload.filters.model_dump(by_alias=True, exclude_none=True),
        artifact_kinds=list(payload.artifact_kinds),
        batch_limit=payload.batch_limit,
        is_active=payload.is_active,
        created_by=actor.id,
    )
    session.add(profile)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        logger.warning(
            "Import profile not created: name already exists name=%r request_id=%s",
            payload.name,
            request_id,
        )
        raise HTTPException(status_code=409, detail="Import profile name already exists") from exc
    await record_event(
        session,
        actor_id=actor.id,
        action="corpus.import_profile.create",
        entity_type="import_profile",
        entity_id=profile.id,
        before=None,
        after={
            "name": profile.name,
            "filters": profile.filters,
            "artifact_kinds": profile.artifact_kinds,
            "batch_limit": profile.batch_limit,
            "is_active": profile.is_active,
        },
        request_id=request_id,
    )
    await session.commit()
    logger.info(
        "Import profile created profile_id=%s name=%r filters=%s artifact_kinds=%s "
        "batch_limit=%s actor_id=%s request_id=%s",
        profile.id,
        profile.name,
        profile.filters,
        profile.artifact_kinds,
        profile.batch_limit,
        actor.id,
        request_id,
    )
    return profile


async def update_import_profile(
    session: AsyncSession,
    profile_id: UUID,
    payload: ImportProfileUpdate,
    actor: ApiClient,
    request_id: str,
) -> ImportProfile:
    profile = await get_import_profile(session, profile_id)
    before = {
        "name": profile.name,
        "filters": profile.filters,
        "artifact_kinds": profile.artifact_kinds,
        "batch_limit": profile.batch_limit,
        "is_active": profile.is_active,
    }
    values: dict[str, object] = {name: getattr(payload, name) for name in payload.model_fields_set}
    if payload.filters is not None and "filters" in values:
        values["filters"] = payload.filters.model_dump(by_alias=True, exclude_none=True)
    for key, value in values.items():
        setattr(profile, key, value)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        logger.warning(
            "Import profile not updated: name already exists profile_id=%s request_id=%s",
            profile_id,
            request_id,
        )
        raise HTTPException(status_code=409, detail="Import profile name already exists") from exc
    after = {**before, **values}
    await record_event(
        session,
        actor_id=actor.id,
        action="corpus.import_profile.update",
        entity_type="import_profile",
        entity_id=profile.id,
        before=before,
        after=after,
        request_id=request_id,
    )
    await session.commit()
    logger.info(
        "Import profile updated profile_id=%s changed=%s actor_id=%s request_id=%s",
        profile.id,
        sorted(key for key in values if before.get(key) != values[key]),
        actor.id,
        request_id,
    )
    return profile


async def enqueue_mining(
    session: AsyncSession,
    *,
    article_id: UUID,
    actor: ApiClient,
    request_id: str,
) -> Job:
    article = await session.scalar(
        select(Article).where(Article.id == article_id).with_for_update()
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.ingest_status != "ready":
        raise HTTPException(status_code=409, detail="Article ingestion is not ready")

    existing = await session.scalar(
        select(Job)
        .where(
            Job.type == "mine_article",
            Job.payload["article_id"].as_string() == str(article_id),
            Job.status.in_(["queued", "processing", "succeeded"]),
        )
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        logger.info(
            "Mining already queued article_id=%s job_id=%s status=%s request_id=%s",
            article_id,
            existing.id,
            existing.status,
            request_id,
        )
        return existing

    job = Job(
        type="mine_article",
        payload={"article_id": str(article_id)},
        status="queued",
        created_by=actor.id,
    )
    session.add(job)
    await session.flush()
    await record_event(
        session,
        actor_id=actor.id,
        action="corpus.article.mine",
        entity_type="job",
        entity_id=job.id,
        after={"article_id": str(article_id)},
        request_id=request_id,
    )
    await session.commit()
    logger.info(
        "Mining job queued job_id=%s article_id=%s actor_id=%s request_id=%s",
        job.id,
        article_id,
        actor.id,
        request_id,
    )
    return job
