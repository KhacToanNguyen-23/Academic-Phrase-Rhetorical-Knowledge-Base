"""Attempt-scoped progress outside the handler transaction; never accepts source text."""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aprkb.core.logging import get_logger
from aprkb.modules.mining.models import Job, JobAttempt

ProgressReporter = Callable[[str, int | None, int | None], Awaitable[None]]
reporter: ContextVar[ProgressReporter | None] = ContextVar("job_progress_reporter", default=None)
STAGES = frozenset(
    {
        "checking_input",
        "listing_articles",
        "checking_duplicates",
        "fetching_content",
        "saving_import_page",
        "checking_rights",
        "reading_content",
        "parsing_document",
        "saving_sentences",
        "loading_sentences",
        "extracting_phrases",
        "saving_candidates",
        "labeling_gold",
    }
)
logger = get_logger(__name__)


class LeaseLost(RuntimeError):
    """Stale attempts must roll back, including their pending ORM output."""


async def report_progress(
    stage: str, completed: int | None = None, total: int | None = None
) -> None:
    callback = reporter.get()
    if callback is not None:
        await callback(stage, completed, total)


def make_reporter(
    factory: async_sessionmaker[AsyncSession], job_id: UUID, token: UUID, attempt_no: int
) -> ProgressReporter:
    async def report(stage: str, completed: int | None, total: int | None) -> None:
        if stage not in STAGES:
            raise ValueError("Unknown progress stage")
        if (completed is None) != (total is None) or (
            completed is not None and total is not None and not 0 <= completed <= total
        ):
            raise ValueError("Invalid progress counters")
        try:
            async with factory() as session:
                owned = await session.scalar(
                    update(Job)
                    .where(
                        Job.id == job_id,
                        Job.status == "processing",
                        Job.lock_token == token,
                    )
                    .values(
                        progress_stage=stage, progress_completed=completed, progress_total=total
                    )
                    .returning(Job.id)
                )
                if owned is None:
                    raise LeaseLost()
                await session.execute(
                    update(JobAttempt)
                    .where(
                        JobAttempt.job_id == job_id,
                        JobAttempt.attempt_no == attempt_no,
                        JobAttempt.ended_at.is_(None),
                    )
                    .values(stage=stage, completed=completed, total=total)
                )
                await session.commit()
        except LeaseLost:
            raise
        except Exception:
            # Monitoring failure must not cause duplicate remote requests or
            # discard good output. The normal final fence remains mandatory.
            logger.warning("Progress unavailable job_id=%s", job_id)

    return report
