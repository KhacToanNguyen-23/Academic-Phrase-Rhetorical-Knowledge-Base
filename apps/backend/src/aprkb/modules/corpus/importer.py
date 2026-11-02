"""Import one page from an external ArticleSource into the corpus ingest path.

Mining rights are checked from listed metadata before any content is downloaded or
stored. Articles with a missing, unknown, or non-mining license are skipped (fail closed).
"""

from dataclasses import asdict, dataclass
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.logging import get_logger
from aprkb.modules.audit.service import record_event
from aprkb.modules.corpus.blobstore import BlobStore
from aprkb.modules.corpus.models import Article, License
from aprkb.modules.corpus.sources import (
    ArticleSource,
    ImportOptions,
    InvalidContentError,
    suffix_for_content_type,
)
from aprkb.modules.mining.models import Job

IMPORT_JOB_TYPE = "import_articles"
MAX_IMPORT_BATCH_LIMIT = 100
logger = get_logger(__name__)


@dataclass
class ImportSummary:
    listed: int = 0
    imported: int = 0
    skipped_license: int = 0
    skipped_duplicate: int = 0
    skipped_format: int = 0
    skipped_invalid_content: int = 0
    next_cursor: str | None = None
    continuation_job_id: str | None = None


async def import_page(
    session: AsyncSession,
    *,
    source: ArticleSource,
    blob_store: BlobStore,
    cursor: str | None,
    limit: int,
    job_id: UUID,
    options: ImportOptions | None = None,
    profile_id: UUID | None = None,
) -> ImportSummary:
    options = options or ImportOptions(filters={}, artifact_kinds=())
    page = await source.list_articles(cursor=cursor, limit=limit, options=options)
    summary = ImportSummary(listed=len(page.articles), next_cursor=page.next_cursor)
    licenses = {row.code: row for row in await session.scalars(select(License))}
    seen_ids: set[str] = set()
    seen_dois: set[str] = set()
    written_keys: list[str] = []
    try:
        for ref in page.articles:
            license_row = licenses.get(ref.license_code) if ref.license_code else None
            if license_row is None or not license_row.allows_mining:
                summary.skipped_license += 1
                logger.info(
                    "Skip %s: license %s does not allow mining", ref.external_id, ref.license_code
                )
                continue
            suffix = suffix_for_content_type(ref.content_type)
            if suffix is None:
                summary.skipped_format += 1
                logger.info(
                    "Skip %s: unsupported content type %r", ref.external_id, ref.content_type
                )
                continue
            if (
                ref.external_id in seen_ids
                or (ref.doi is not None and ref.doi in seen_dois)
                or await _already_imported(session, source.name, ref.external_id, ref.doi)
            ):
                summary.skipped_duplicate += 1
                logger.info("Skip %s: already imported", ref.external_id)
                continue
            seen_ids.add(ref.external_id)
            if ref.doi is not None:
                seen_dois.add(ref.doi)

            try:
                content = await source.fetch_content(ref)
            except InvalidContentError as error:
                summary.skipped_invalid_content += 1
                # InvalidContentError messages are fixed strings written by the adapters.
                logger.info("Skip %s: invalid content (%s)", ref.external_id, error)
                continue
            article_id = uuid4()
            blob_key = f"articles/{article_id.hex}{suffix}"
            blob_store.put(blob_key, content)
            written_keys.append(blob_key)
            session.add(
                Article(
                    id=article_id,
                    source=source.name,
                    external_id=ref.external_id,
                    doi=ref.doi,
                    title=ref.title,
                    license_id=license_row.id,
                    blob_key=blob_key,
                    ingest_status="pending",
                )
            )
            session.add(
                Job(
                    type="ingest_article",
                    payload={"article_id": str(article_id)},
                    status="queued",
                )
            )
            summary.imported += 1
            logger.info(
                "Imported %s as article_id=%s license=%s blob=%s bytes=%s",
                ref.external_id,
                article_id,
                license_row.code,
                blob_key,
                len(content),
            )

        if page.next_cursor is not None:
            continuation = Job(
                type=IMPORT_JOB_TYPE,
                payload={
                    "source": source.name,
                    "cursor": page.next_cursor,
                    "limit": limit,
                    "profile_id": str(profile_id) if profile_id else None,
                    "filters": dict(options.filters),
                    "artifact_kinds": list(options.artifact_kinds),
                },
                status="queued",
            )
            session.add(continuation)
            await session.flush()
            summary.continuation_job_id = str(continuation.id)
        else:
            await session.flush()

        await record_event(
            session,
            actor_id=None,
            action="corpus.import.page",
            entity_type="job",
            entity_id=job_id,
            after={
                "source": source.name,
                "profile_id": str(profile_id) if profile_id else None,
                **asdict(summary),
            },
            request_id=f"job:{job_id}",
        )
    except BaseException:
        # The transaction rolls back, so blobs written for this page must go too.
        for key in written_keys:
            blob_store.delete(key)
        raise
    return summary


async def _already_imported(
    session: AsyncSession, source_name: str, external_id: str, doi: str | None
) -> bool:
    condition: ColumnElement[bool] = (Article.source == source_name) & (
        Article.external_id == external_id
    )
    if doi is not None:
        condition = or_(condition, Article.doi == doi)
    return await session.scalar(select(Article.id).where(condition).limit(1)) is not None
