"""PostgreSQL polling runner; each claimed job is committed before processing."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aprkb.core.config import settings
from aprkb.modules.corpus.blobstore import BlobStore
from aprkb.modules.mining.models import Job
from aprkb.modules.mining.queue import claim_next
from aprkb.worker.handlers import ArticleSourceFactory, handle_job, local_blob_store


async def run_once(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    blob_store: BlobStore | None = None,
    article_source_factory: ArticleSourceFactory | None = None,
) -> bool:
    """Claim and handle at most one job. Return False when the queue is empty."""
    async with session_factory() as session:
        job = await claim_next(session)
        if job is None:
            await session.rollback()
            return False
        job_id = job.id
        job_type = job.type
        await session.commit()

    store = blob_store or local_blob_store()
    try:
        async with session_factory() as session:
            job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job is None or job.status != "processing":
                return True
            if article_source_factory is None:
                error = await handle_job(session, job, store)
            else:
                error = await handle_job(
                    session, job, store, article_source_factory=article_source_factory
                )
            job.status = "failed" if error else "succeeded"
            job.error = error
            job.locked_at = None
            await session.commit()
    except Exception as error:
        # Do not copy arbitrary exception text into persistent logs; it can include input data.
        safe_error = f"Processing failed ({type(error).__name__})"
        async with session_factory() as session:
            job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job is not None:
                job.status = "failed"
                job.error = safe_error
                job.locked_at = None
                if job_type == "ingest_article":
                    article_id_value = job.payload.get("article_id")
                    if isinstance(article_id_value, str):
                        from uuid import UUID

                        from aprkb.modules.corpus.models import Article

                        try:
                            article = await session.get(Article, UUID(article_id_value))
                        except ValueError:
                            article = None
                        if article is not None:
                            article.ingest_status = "failed"
            await session.commit()
    return True


async def run_forever() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        while True:
            if not await run_once(session_factory):
                await asyncio.sleep(0.5)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
