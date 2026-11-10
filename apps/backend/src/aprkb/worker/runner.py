"""PostgreSQL polling runner; each claimed job is committed before processing."""

import asyncio
import contextlib
import signal
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aprkb.core.config import settings
from aprkb.core.logging import configure_logging, get_logger, safe_traceback
from aprkb.modules import load_models
from aprkb.modules.corpus.blobstore import BlobStore
from aprkb.modules.corpus.models import Article
from aprkb.modules.mining.models import Job
from aprkb.modules.mining.operations import finish_attempt
from aprkb.modules.mining.queue import claim_next, execution_lock
from aprkb.worker.handlers import (
    ArticleSourceFactory,
    WorkerNlpRuntime,
    handle_job,
    initialize_worker_nlp_runtime,
    local_blob_store,
)
from aprkb.worker.progress import LeaseLost, make_reporter, reporter
from aprkb.worker.retry import classify_failure, retry_delay

logger = get_logger(__name__)


class _AttemptBlobs:
    """Compensate files created by an attempt whose database transaction rolls back."""

    def __init__(self, store: BlobStore) -> None:
        self.store = store
        self.written: set[str] = set()

    def put(self, key: str, content: bytes) -> None:
        self.written.add(key)
        self.store.put(key, content)

    def get(self, key: str) -> bytes:
        return self.store.get(key)

    def delete(self, key: str) -> None:
        self.store.delete(key)
        self.written.discard(key)

    def cleanup(self) -> None:
        for key in tuple(self.written):
            try:
                self.delete(key)
            except OSError:
                logger.error("Could not compensate attempt blob")


async def heartbeat(factory: async_sessionmaker[AsyncSession], job_id: UUID, token: UUID) -> bool:
    async with factory() as session:
        result = await session.scalar(
            update(Job)
            .where(Job.id == job_id, Job.status == "processing", Job.lock_token == token)
            .values(locked_at=datetime.now(UTC))
            .returning(Job.id)
        )
        await session.commit()
        return result is not None


async def _heartbeat_loop(
    factory: async_sessionmaker[AsyncSession], job_id: UUID, token: UUID
) -> None:
    while True:
        await asyncio.sleep(settings.job_heartbeat_seconds)
        try:
            if not await heartbeat(factory, job_id, token):
                return
        except Exception:
            # The execution advisory lock still prevents takeover while the
            # transaction is alive. Final ownership is checked before commit.
            logger.warning("Heartbeat unavailable job_id=%s", job_id)


async def record_failure(
    factory: async_sessionmaker[AsyncSession],
    *,
    job_id: UUID,
    token: UUID,
    error: Exception,
) -> None:
    failure = classify_failure(error)
    async with factory() as session:
        job = await session.scalar(
            select(Job)
            .where(
                Job.id == job_id,
                Job.status == "processing",
                Job.lock_token == token,
            )
            .with_for_update()
        )
        if job is None:
            return
        # Only the three transactional, read-only-source handlers are opted in.
        retry = (
            failure.retryable
            and job.type
            in {
                "import_articles",
                "ingest_article",
                "mine_article",
            }
            and job.attempts < job.max_attempts
        )
        job.status = "queued" if retry else "failed"
        job.error_code = failure.code
        job.error = f"Processing failed ({type(error).__name__})"
        job.locked_at = None
        job.lock_token = None
        job.result = None
        job.next_attempt_at = (
            datetime.now(UTC)
            + timedelta(
                seconds=retry_delay(
                    job.attempts,
                    base=settings.job_retry_base_seconds,
                    cap=settings.job_retry_cap_seconds,
                    retry_after=failure.retry_after,
                )
            )
            if retry
            else None
        )
        if job.type == "ingest_article":
            article_value = job.payload.get("article_id")
            try:
                article_id = UUID(str(article_value))
            except ValueError:
                article_id = None
            article = await session.get(Article, article_id) if article_id else None
            if article is not None and article.ingest_status != "ready":
                article.ingest_status = "pending" if retry else "failed"
        await finish_attempt(session, job, outcome="failed")
        await session.commit()
        logger.warning(
            "Job attempt failed job_id=%s code=%s retry=%s attempt=%s/%s",
            job_id,
            failure.code,
            retry,
            job.attempts,
            job.max_attempts,
        )


async def _committed_after_uncertain_ack(
    factory: async_sessionmaker[AsyncSession], job_id: UUID
) -> bool | None:
    # COMMIT can reach PostgreSQL even if its acknowledgement is lost. Never
    # delete referenced blobs or mark a committed success failed in that case.
    try:
        async with factory() as session:
            status = await session.scalar(select(Job.status).where(Job.id == job_id))
            return status in {"succeeded", "failed"}
    except Exception:
        logger.warning("Commit outcome unknown; retaining attempt blobs job_id=%s", job_id)
        return None


async def run_once(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    blob_store: BlobStore | None = None,
    article_source_factory: ArticleSourceFactory | None = None,
    nlp_runtime: WorkerNlpRuntime | None = None,
) -> bool:
    """Claim one due attempt; commit output and success atomically under ownership."""
    async with session_factory() as session:
        job = await claim_next(session, stale_after_seconds=settings.job_lease_seconds)
        if job is None:
            # claim_next may have terminalized exhausted stale jobs.
            await session.commit()
            return False
        job_id, job_type, token, attempt_no = job.id, job.type, job.lock_token, job.attempts
        assert token is not None
        await session.commit()
    logger.info("Job claimed job_id=%s type=%s", job_id, job_type)
    started = time.perf_counter()
    store = _AttemptBlobs(blob_store or local_blob_store())
    pulse = asyncio.create_task(_heartbeat_loop(session_factory, job_id, token))
    committing = False
    progress_token = reporter.set(make_reporter(session_factory, job_id, token, attempt_no))
    try:
        async with session_factory() as session:
            if not await execution_lock(session, f"job:{job_id}"):
                return True
            job = await session.scalar(select(Job).where(Job.id == job_id))
            if job is None or job.status != "processing" or job.lock_token != token:
                return True
            async with asyncio.timeout(settings.job_timeout_seconds):
                if article_source_factory is None and nlp_runtime is None:
                    error = await handle_job(session, job, store)
                elif article_source_factory is None:
                    error = await handle_job(session, job, store, nlp_runtime=nlp_runtime)
                elif nlp_runtime is None:
                    error = await handle_job(
                        session, job, store, article_source_factory=article_source_factory
                    )
                else:
                    error = await handle_job(
                        session,
                        job,
                        store,
                        article_source_factory=article_source_factory,
                        nlp_runtime=nlp_runtime,
                    )
            # Check without autoflush: a stale attempt must never publish even
            # its pending ORM result. The advisory lock excludes compliant reclaimers.
            with session.no_autoflush:
                owned = await session.scalar(
                    select(Job.id)
                    .where(
                        Job.id == job_id,
                        Job.status == "processing",
                        Job.lock_token == token,
                    )
                    .with_for_update()
                )
            if owned is None:
                raise LeaseLost()
            job.status = "failed" if error else "succeeded"
            job.error = error
            job.error_code = "handler_rejected" if error else None
            job.locked_at = None
            job.lock_token = None
            job.next_attempt_at = None
            if not error:
                job.progress_stage = "completed"
            await finish_attempt(session, job, outcome="failed" if error else "succeeded")
            committing = True
            await session.commit()
        logger.info(
            "Job finished job_id=%s type=%s failed=%s elapsed_ms=%.0f",
            job_id,
            job_type,
            bool(error),
            (time.perf_counter() - started) * 1000,
        )
    except asyncio.CancelledError:
        if not committing or await _committed_after_uncertain_ack(session_factory, job_id) is False:
            store.cleanup()
        # Leave processing for bounded lease recovery after abrupt shutdown.
        raise
    except LeaseLost:
        store.cleanup()
        logger.warning("Discarded stale attempt job_id=%s", job_id)
    except Exception as error:
        if committing:
            applied = await _committed_after_uncertain_ack(session_factory, job_id)
            if applied is not False:
                return True
        store.cleanup()
        logger.error("Job crashed job_id=%s type=%s %s", job_id, job_type, safe_traceback(error))
        await record_failure(session_factory, job_id=job_id, token=token, error=error)
    finally:
        reporter.reset(progress_token)
        pulse.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pulse
    return True


async def run_forever() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    nlp_runtime = initialize_worker_nlp_runtime()
    logger.info(
        "Worker started env=%s article_source=%s", settings.app_env, settings.article_source
    )
    # Deployment rollout/drain relies on SIGTERM stopping polling before the current job
    # finishes, instead of the default signal behavior that kills the process mid-job.
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    try:
        while not stop.is_set():
            if not await run_once(session_factory, nlp_runtime=nlp_runtime):
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=0.5)
    finally:
        await engine.dispose()
        logger.info("Worker stopped")


def main() -> None:
    configure_logging()
    # Article has foreign keys into journals and taxonomy; without every model registered the
    # first flush in a standalone worker fails with NoReferencedTableError.
    load_models()
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_forever())


if __name__ == "__main__":
    main()
