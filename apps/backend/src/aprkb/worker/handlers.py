"""Transactional handlers for ingestion and mining jobs."""

from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.config import settings
from aprkb.modules.corpus.blobstore import BlobStore, LocalBlobStore
from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.corpus.parsers.base import DocumentParser
from aprkb.modules.corpus.parsers.jats_parser import JatsParserStub
from aprkb.modules.corpus.parsers.pdf_parser import PdfParserStub
from aprkb.modules.corpus.parsers.text_parser import TextParser
from aprkb.modules.corpus.section_detector import detect_section
from aprkb.modules.corpus.sentence_splitter import split_sentences
from aprkb.modules.mining.candidate_writer import CandidateDraft, CandidateWriter
from aprkb.modules.mining.models import Candidate, Job
from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.policies.loader import load_policy_bundle

_PARSERS: tuple[DocumentParser, ...] = (TextParser(), JatsParserStub(), PdfParserStub())


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


async def handle_job(session: AsyncSession, job: Job, blob_store: BlobStore) -> str | None:
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
    section = min(section_rows.values(), key=lambda row: row.order) if section_rows else None
    for span in split_sentences(document.raw_text):
        session.add(
            Sentence(
                article_id=article.id,
                article_section_id=section.id if section is not None else None,
                text=span.text,
                char_start=span.char_start,
                char_end=span.char_end,
            )
        )
    article.ingest_status = "ready"
    return None


def _mime_from_key(blob_key: str) -> str:
    suffix = Path(blob_key).suffix.casefold()
    return {
        ".txt": "text/plain",
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
