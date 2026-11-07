"""Shared import/upload duplicate checks, including legacy blob fingerprints."""

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from aprkb.core.logging import get_logger
from aprkb.modules.corpus.blobstore import BlobStore
from aprkb.modules.corpus.identity import content_hash, normalize_doi, title_identity
from aprkb.modules.corpus.models import Article, License
from aprkb.modules.corpus.parsers.pdf_parser import PARSER_VERSION, PdfInputError, inspect_pdf

logger = get_logger(__name__)


@dataclass
class DuplicateMatch:
    article: Article
    reason: str

    def detail(self, *, external_id: str | None, title: str | None) -> dict[str, str | None]:
        return {
            "external_id": external_id,
            "title": title,
            "reason": self.reason,
            "matched_article_id": str(self.article.id),
            "matched_title": self.article.title,
            "matched_source": self.article.source,
            "matched_status": self.article.ingest_status,
        }


async def lock_corpus_writes(session: AsyncSession) -> None:
    # One transaction lock shared by import and upload. Page size is bounded to 100.
    # This also gives legacy hash backfill and check+insert a single lock order.
    await session.execute(text("SELECT pg_advisory_xact_lock(18421, 1)"))


async def find_metadata_duplicate(
    session: AsyncSession, *, source: str, external_id: str | None, doi: str | None
) -> DuplicateMatch | None:
    if external_id is not None:
        article = await session.scalar(
            select(Article)
            .where(Article.source == source, Article.external_id == external_id)
            .limit(1)
        )
        if article is not None:
            return DuplicateMatch(article, "source_id")
    if key := normalize_doi(doi):
        article = await session.scalar(
            select(Article)
            .where(Article.doi_key == key)
            .order_by(Article.created_at, Article.id)
            .limit(1)
        )
        if article is not None:
            return DuplicateMatch(article, "doi")
    return None


async def find_title_candidates(session: AsyncSession, title: str | None) -> list[DuplicateMatch]:
    key = title_identity(title)
    if key is None:
        return []
    rows = await session.scalars(
        select(Article)
        .where(Article.title_key == key)
        .order_by(Article.created_at, Article.id)
        .limit(5)
    )
    # Even conflicting DOIs can describe versions; report them without merging.
    return [DuplicateMatch(article, "title") for article in rows]


async def find_content_duplicate(
    session: AsyncSession, digest: str, blob_store: BlobStore
) -> DuplicateMatch | None:
    article = await session.scalar(
        select(Article)
        .where(Article.content_sha256 == digest)
        .order_by(Article.created_at, Article.id)
        .limit(1)
    )
    if article is not None:
        return DuplicateMatch(article, "file_sha256")
    # Migrations cannot access the blob store. Populate old hashes lazily, once,
    # under the same corpus write lock. Missing blobs do not prove a duplicate.
    rows = await session.scalars(select(Article).where(Article.content_sha256.is_(None)))
    match = None
    for article in rows:
        try:
            article.content_sha256 = content_hash(blob_store.get(article.blob_key))
        except FileNotFoundError:
            logger.warning("Cannot fingerprint missing legacy blob article_id=%s", article.id)
            continue
        if article.content_sha256 == digest and match is None:
            match = DuplicateMatch(article, "file_sha256")
    return match


async def find_pdf_text_duplicate(
    session: AsyncSession, digest: str, blob_store: BlobStore
) -> DuplicateMatch | None:
    """Compare full PDF extracted text, including legacy PDFs, under the corpus lock."""
    article = await session.scalar(
        select(Article)
        .where(Article.pdf_text_sha256 == digest)
        .order_by(Article.created_at, Article.id)
        .limit(1)
    )
    if article is not None:
        return DuplicateMatch(article, "pdf_text_sha256")
    rows = await session.scalars(
        select(Article)
        .join(License, License.id == Article.license_id)
        .where(Article.pdf_text_sha256.is_(None), Article.blob_key.ilike("%.pdf"))
        .where(License.allows_mining.is_(True))
        .order_by(Article.created_at, Article.id)
    )
    match = None
    for article in rows:
        try:
            content = blob_store.get(article.blob_key)
            info = await run_in_threadpool(inspect_pdf, content)
        except (FileNotFoundError, PdfInputError):
            logger.warning("Cannot fingerprint legacy PDF article_id=%s", article.id)
            continue
        article.pdf_text_sha256 = info.text_sha256
        article.page_count = info.page_count
        article.parser_version = PARSER_VERSION
        if info.text_sha256 == digest and match is None:
            match = DuplicateMatch(article, "pdf_text_sha256")
    return match
