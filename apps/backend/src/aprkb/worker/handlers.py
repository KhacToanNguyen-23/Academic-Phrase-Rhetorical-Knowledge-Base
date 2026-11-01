"""Transactional handlers for import, ingestion, and mining jobs."""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.config import settings
from aprkb.core.logging import get_logger
from aprkb.modules.corpus.blobstore import BlobStore, LocalBlobStore
from aprkb.modules.corpus.importer import IMPORT_JOB_TYPE, MAX_IMPORT_BATCH_LIMIT, import_page
from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.corpus.parsers.base import DocumentParser
from aprkb.modules.corpus.parsers.jats_parser import JatsParserStub
from aprkb.modules.corpus.parsers.markdown_parser import MarkdownParser
from aprkb.modules.corpus.parsers.pdf_parser import PdfParserStub
from aprkb.modules.corpus.parsers.text_parser import TextParser
from aprkb.modules.corpus.schemas import DEFAULT_ARTIFACT_KINDS, SlrWorkFilters
from aprkb.modules.corpus.section_detector import SectionDetector
from aprkb.modules.corpus.sentence_splitter import split_sentences
from aprkb.modules.corpus.sources import ArticleSource, build_article_source
from aprkb.modules.corpus.sources.base import ImportOptions
from aprkb.modules.mining.candidate_writer import CandidateDraft, CandidateWriter
from aprkb.modules.mining.models import Candidate, Job
from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.policies.loader import load_policy_bundle

_PARSERS: tuple[DocumentParser, ...] = (
    TextParser(),
    MarkdownParser(),
    JatsParserStub(),
    PdfParserStub(),
)
ArticleSourceFactory = Callable[[str], ArticleSource]
logger = get_logger(__name__)


class _SessionCandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def create_candidate(self, draft: CandidateDraft) -> Candidate:
        candidate = Candidate(
            canonical_frame=draft.canonical_frame,
            source_sentence_ids=draft.source_sentence_ids,
            slots=draft.slots,
            confidence=draft.confidence,
            epistemic_strength=draft.epistemic_strength,
            status="pending",
        )
        self._session.add(candidate)
        return candidate


async def handle_job(
    session: AsyncSession,
    job: Job,
    blob_store: BlobStore,
    *,
    article_source_factory: ArticleSourceFactory = build_article_source,
) -> str | None:
    if job.type == IMPORT_JOB_TYPE:
        return await _import(session, job, blob_store, article_source_factory)
    article_value = job.payload.get("article_id")
    if not isinstance(article_value, str):
        return "Job payload is missing article_id"
    try:
        article_id = UUID(article_value)
    except ValueError:
        return "Job payload contains an invalid article_id"

    article = await session.get(Article, article_id)
    if article is None:
        return "Article not found"
    if job.type == "ingest_article":
        return await _ingest(session, article, blob_store)
    if job.type == "mine_article":
        return await _mine(session, article)
    return "Unknown job type"


async def _import(
    session: AsyncSession,
    job: Job,
    blob_store: BlobStore,
    article_source_factory: ArticleSourceFactory,
) -> str | None:
    source_name = job.payload.get("source")
    cursor = job.payload.get("cursor")
    limit = job.payload.get("limit")
    if not isinstance(source_name, str):
        return "Job payload is missing source"
    if cursor is not None and not isinstance(cursor, str):
        return "Job payload contains an invalid cursor"
    if not isinstance(limit, int) or not 1 <= limit <= MAX_IMPORT_BATCH_LIMIT:
        return "Job payload contains an invalid limit"
    try:
        raw_filters = job.payload.get("filters", {})
        raw_kinds = job.payload.get("artifact_kinds", list(DEFAULT_ARTIFACT_KINDS))
        profile_value = job.payload.get("profile_id")
        if not isinstance(raw_filters, dict) or not isinstance(raw_kinds, list):
            return "Job payload contains invalid import options"
        filters = SlrWorkFilters.model_validate(raw_filters).model_dump(
            by_alias=True, exclude_none=True
        )
        if (
            any(kind not in DEFAULT_ARTIFACT_KINDS for kind in raw_kinds)
            or not raw_kinds
            or len(set(raw_kinds)) != len(raw_kinds)
        ):
            return "Job payload contains invalid artifact kinds"
        profile_id = UUID(profile_value) if isinstance(profile_value, str) else None
    except (ValueError, TypeError):
        return "Job payload contains invalid import options"
    try:
        source = article_source_factory(source_name)
    except ValueError as error:
        if str(error) == "SLR_API_KEY is required when ARTICLE_SOURCE=slr":
            return str(error)
        return "Unknown article source"
    # Keep a failed page atomic while leaving the outer transaction available to
    # mark the import job failed. import_page compensates any blobs it wrote.
    try:
        async with session.begin_nested():
            summary = await import_page(
                session,
                source=source,
                blob_store=blob_store,
                cursor=cursor,
                limit=limit,
                job_id=job.id,
                options=ImportOptions(filters, tuple(raw_kinds)),
                profile_id=profile_id,
            )
            job.result = {**asdict(summary), "profile_id": str(profile_id) if profile_id else None}
        logger.info(
            "Import page done job_id=%s source=%s profile_id=%s filters=%s listed=%s imported=%s "
            "skipped_license=%s skipped_format=%s skipped_duplicate=%s "
            "skipped_invalid_content=%s continuation_job_id=%s",
            job.id,
            source_name,
            profile_id,
            filters,
            summary.listed,
            summary.imported,
            summary.skipped_license,
            summary.skipped_format,
            summary.skipped_duplicate,
            summary.skipped_invalid_content,
            summary.continuation_job_id,
        )
    finally:
        close = getattr(source, "aclose", None)
        if close is not None:
            await close()
    return None


async def _ingest(session: AsyncSession, article: Article, blob_store: BlobStore) -> str | None:
    license_row = await session.get(License, article.license_id)
    if license_row is None or not license_row.allows_mining:
        article.ingest_status = "rejected"
        return "Article license does not allow mining"

    content = blob_store.get(article.blob_key)
    parser = next(
        (
            candidate
            for candidate in _PARSERS
            if candidate.supports(_mime_from_key(article.blob_key))
        ),
        None,
    )
    if parser is None:
        article.ingest_status = "failed"
        return "Unsupported article format"
    document = parser.parse(content)
    policies = load_policy_bundle()
    section_codes = SectionDetector(policies.section_headings).detect(document.sections)
    abbreviations = policies.abbreviations.abbreviations
    section_rows: dict[int, ArticleSection] = {}
    for parsed_section, section_code in zip(document.sections, section_codes, strict=True):
        section_row = ArticleSection(
            article_id=article.id,
            section_code=section_code,
            heading=parsed_section.heading,
            order=parsed_section.order,
        )
        session.add(section_row)
        section_rows[parsed_section.order] = section_row
    await session.flush()
    for parsed_section in document.sections:
        section_row = section_rows[parsed_section.order]
        for span in split_sentences(parsed_section.text, abbreviations=abbreviations):
            session.add(
                Sentence(
                    article_id=article.id,
                    article_section_id=section_row.id,
                    text=span.text,
                    char_start=parsed_section.char_start + span.char_start,
                    char_end=parsed_section.char_start + span.char_end,
                )
            )
    article.ingest_status = "ready"
    return None


@dataclass(frozen=True)
class ReingestResult:
    status: str
    sentences_before: int = 0
    sentences_after: int = 0
    pending_candidates_removed: int = 0
    error: str | None = None


async def reingest_article(
    session: AsyncSession, article: Article, blob_store: BlobStore
) -> ReingestResult:
    """Replace an article's sections and sentences after splitter or detector changes.

    Pending candidates that point at the old sentences are removed with them. Articles
    with reviewed candidates are left untouched so review history keeps valid sources.
    The caller owns the transaction.
    """
    old_ids = list(
        await session.scalars(select(Sentence.id).where(Sentence.article_id == article.id))
    )
    linked = (
        list(
            await session.scalars(
                select(Candidate).where(Candidate.source_sentence_ids.overlap(old_ids))
            )
        )
        if old_ids
        else []
    )
    if any(candidate.status != "pending" for candidate in linked):
        return ReingestResult(status="skipped_reviewed_candidates", sentences_before=len(old_ids))
    for candidate in linked:
        await session.delete(candidate)
    await session.execute(delete(Sentence).where(Sentence.article_id == article.id))
    await session.execute(delete(ArticleSection).where(ArticleSection.article_id == article.id))
    await session.flush()
    error = await _ingest(session, article, blob_store)
    await session.flush()
    after = len(
        list(await session.scalars(select(Sentence.id).where(Sentence.article_id == article.id)))
    )
    return ReingestResult(
        status="failed" if error else "ready",
        sentences_before=len(old_ids),
        sentences_after=after,
        pending_candidates_removed=len(linked),
        error=error,
    )


def _mime_from_key(blob_key: str) -> str:
    suffix = Path(blob_key).suffix.casefold()
    return {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".xml": "application/xml",
        ".jats": "application/jats+xml",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")


async def _mine(session: AsyncSession, article: Article) -> str | None:
    if article.ingest_status != "ready":
        return "Article ingestion is not ready"
    rows = list(
        await session.execute(
            select(Sentence, ArticleSection.section_code)
            .outerjoin(ArticleSection, Sentence.article_section_id == ArticleSection.id)
            .where(Sentence.article_id == article.id)
            .order_by(Sentence.char_start)
        )
    )
    if not rows:
        return "Article has no parsed sentences"
    policy = load_policy_bundle().mining_filter
    pipeline = MiningPipeline(stages=build_stages(policy=policy))
    items = pipeline.process(
        [
            MiningItem(text=sentence.text, source_sentence_ids=[sentence.id], section_code=code)
            for sentence, code in rows
        ]
    )
    writer = CandidateWriter(_SessionCandidateRepository(session))
    for item in items:
        writer.write(
            CandidateDraft(canonical_frame=item.text, source_sentence_ids=item.source_sentence_ids)
        )
    return None


def local_blob_store() -> LocalBlobStore:
    return LocalBlobStore(settings.blob_dir)
