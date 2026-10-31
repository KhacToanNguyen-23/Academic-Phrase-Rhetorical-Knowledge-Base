"""Persistence operations for article upload and mining enqueue requests."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.corpus.importer import IMPORT_JOB_TYPE
from aprkb.modules.corpus.models import Article, License
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.models import Job


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
) -> tuple[Article, Job]:
    article = Article(
        id=article_id,
        source="upload",
        title=title,
        license_id=license_row.id,
        blob_key=blob_key,
        ingest_status="pending",
        created_by=actor.id,
    )
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
    return article, job


async def enqueue_import(
    session: AsyncSession,
    *,
    source_name: str,
    cursor: str | None,
    limit: int,
    actor: ApiClient,
    request_id: str,
) -> Job:
    if source_name == "null":
        raise HTTPException(status_code=409, detail="No article source is configured")
    job = Job(
        type=IMPORT_JOB_TYPE,
        payload={"source": source_name, "cursor": cursor, "limit": limit},
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
        after={"source": source_name, "cursor": cursor, "limit": limit},
        request_id=request_id,
    )
    await session.commit()
    return job


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
    return job
