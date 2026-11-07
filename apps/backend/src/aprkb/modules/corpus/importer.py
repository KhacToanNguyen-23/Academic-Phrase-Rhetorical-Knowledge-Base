"""Import one page from an external ArticleSource into the corpus ingest path.

Mining rights are checked from listed metadata before any content is downloaded or
stored. Articles with a missing, unknown, or non-mining license are skipped (fail closed).
"""

from dataclasses import asdict, dataclass, field
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from aprkb.core.logging import get_logger
from aprkb.modules.audit.service import record_event
from aprkb.modules.corpus.blobstore import BlobStore
from aprkb.modules.corpus.dedup import (
    find_content_duplicate,
    find_metadata_duplicate,
    find_pdf_text_duplicate,
    find_title_candidates,
    lock_corpus_writes,
)
from aprkb.modules.corpus.identity import content_hash
from aprkb.modules.corpus.models import Article, License
from aprkb.modules.corpus.parsers.pdf_parser import PARSER_VERSION, PdfInputError, inspect_pdf
from aprkb.modules.corpus.sources import (
    ArticleSource,
    ImportOptions,
    InvalidContentError,
    suffix_for_content_type,
)
from aprkb.modules.mining.models import Job
from aprkb.worker.progress import report_progress

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
    duplicates: list[dict[str, str | None]] = field(default_factory=list)
    suspected_duplicates: list[dict[str, str | None]] = field(default_factory=list)
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
    batch_id: UUID | None = None,
) -> ImportSummary:
    options = options or ImportOptions(filters={}, artifact_kinds=())
    batch_id = batch_id or job_id
    await report_progress("listing_articles")
    page = await source.list_articles(cursor=cursor, limit=limit, options=options)
    await report_progress("checking_duplicates", 0, len(page.articles))
    await lock_corpus_writes(session)
    summary = ImportSummary(listed=len(page.articles), next_cursor=page.next_cursor)
    licenses = {row.code: row for row in await session.scalars(select(License))}
    written_keys: list[str] = []
    try:
        for index, ref in enumerate(page.articles):
            await report_progress("checking_duplicates", index, len(page.articles))
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
            match = await find_metadata_duplicate(
                session, source=source.name, external_id=ref.external_id, doi=ref.doi
            )
            if match is not None:
                summary.skipped_duplicate += 1
                summary.duplicates.append(
                    match.detail(external_id=ref.external_id, title=ref.title)
                )
                continue
            candidates = await find_title_candidates(session, ref.title)

            try:
                await report_progress("fetching_content", index, len(page.articles))
                content = await source.fetch_content(ref)
            except InvalidContentError as error:
                summary.skipped_invalid_content += 1
                # InvalidContentError messages are fixed strings written by the adapters.
                logger.info("Skip %s: invalid content (%s)", ref.external_id, error)
                continue
            digest = content_hash(content)
            pdf = None
            if suffix == ".pdf":
                try:
                    pdf = await run_in_threadpool(inspect_pdf, content)
                except PdfInputError:
                    summary.skipped_invalid_content += 1
                    continue
            match = await find_content_duplicate(session, digest, blob_store)
            if match is None and pdf is not None:
                match = await find_pdf_text_duplicate(session, pdf.text_sha256, blob_store)
            if match is not None:
                summary.skipped_duplicate += 1
                summary.duplicates.append(
                    match.detail(external_id=ref.external_id, title=ref.title)
                )
                continue
            for candidate in candidates:
                summary.suspected_duplicates.append(
                    candidate.detail(external_id=ref.external_id, title=ref.title)
                )
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
                    content_sha256=digest,
                    pdf_text_sha256=pdf.text_sha256 if pdf else None,
                    page_count=pdf.page_count if pdf else None,
                    parser_version=PARSER_VERSION if pdf else None,
                    metadata_provenance={
                        "method": "source-metadata",
                        "source": source.name,
                        "pdf_suggestions": {
                            "title": pdf.title,
                            "authors": list(pdf.authors),
                            "doi_candidates": list(pdf.doi_candidates),
                        }
                        if pdf
                        else {},
                    },
                    title=ref.title,
                    license_id=license_row.id,
                    blob_key=blob_key,
                    ingest_status="pending",
                    import_batch_id=batch_id,
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

        await report_progress("saving_import_page", len(page.articles), len(page.articles))
        if page.next_cursor is not None:
            continuation = Job(
                type=IMPORT_JOB_TYPE,
                payload={
                    "source": source.name,
                    "cursor": page.next_cursor,
                    "limit": limit,
                    "profile_id": str(profile_id) if profile_id else None,
                    "batch_id": str(batch_id),
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
