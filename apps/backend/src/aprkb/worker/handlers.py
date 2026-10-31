"""Transactional handlers for import, ingestion, and mining jobs."""

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.config import settings
from aprkb.modules.corpus.blobstore import BlobStore, LocalBlobStore
from aprkb.modules.corpus.importer import IMPORT_JOB_TYPE, MAX_IMPORT_BATCH_LIMIT, import_page
from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.corpus.parsers.base import DocumentParser
from aprkb.modules.corpus.parsers.jats_parser import JatsParserStub
from aprkb.modules.corpus.parsers.markdown_parser import MarkdownParser
from aprkb.modules.corpus.parsers.pdf_parser import PdfParserStub
from aprkb.modules.corpus.parsers.text_parser import TextParser
from aprkb.modules.corpus.section_detector import detect_section
from aprkb.modules.corpus.sentence_splitter import split_sentences
from aprkb.modules.corpus.sources import ArticleSource, build_article_source
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
        source = article_source_factory(source_name)
    except ValueError:
        return "Unknown article source"
    # Keep a failed page atomic while leaving the outer transaction available to
    # mark the import job failed. import_page compensates any blobs it wrote.
    async with session.begin_nested():
        await import_page(
            session, source=source, blob_store=blob_store, cursor=cursor, limit=limit, job_id=job.id
        )
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
    section_rows: dict[int, ArticleSection] = {}
    for parsed_section in document.sections:
        section_row = ArticleSection(
            article_id=article.id,
            section_code=detect_section(parsed_section),
            heading=parsed_section.heading,
            order=parsed_section.order,
        )
        session.add(section_row)
        section_rows[parsed_section.order] = section_row
    await session.flush()
    for parsed_section in document.sections:
        section_row = section_rows[parsed_section.order]
        for span in split_sentences(parsed_section.text):
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
    sentences = list(
        await session.scalars(
            select(Sentence).where(Sentence.article_id == article.id).order_by(Sentence.char_start)
        )
    )
    if not sentences:
        return "Article has no parsed sentences"
    policy = load_policy_bundle().mining_filter
    pipeline = MiningPipeline(stages=build_stages(policy=policy))
    items = pipeline.process(
        [MiningItem(text=row.text, source_sentence_ids=[row.id]) for row in sentences]
    )
    writer = CandidateWriter(_SessionCandidateRepository(session))
    for item in items:
        writer.write(
            CandidateDraft(canonical_frame=item.text, source_sentence_ids=item.source_sentence_ids)
        )
    return None


def local_blob_store() -> LocalBlobStore:
    return LocalBlobStore(settings.blob_dir)
