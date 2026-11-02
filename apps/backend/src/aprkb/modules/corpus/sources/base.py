"""Contracts for external article sources polled by the import worker (ADR-0005)."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SourceArticleRef:
    """Metadata listed by a source. Content is fetched only after the license check."""

    external_id: str
    title: str | None
    doi: str | None
    license_code: str | None
    content_type: str


@dataclass(frozen=True)
class SourcePage:
    articles: tuple[SourceArticleRef, ...]
    next_cursor: str | None


class ArticleSource(Protocol):
    name: str

    async def list_articles(self, *, cursor: str | None, limit: int) -> SourcePage: ...

    async def fetch_content(self, article: SourceArticleRef) -> bytes: ...


# Content types the ingest worker can store; the suffix selects the parser later.
CONTENT_TYPE_SUFFIXES = {
    "application/pdf": ".pdf",
    "text/markdown": ".md",
    "text/x-markdown": ".md",
    "text/plain": ".txt",
}


def suffix_for_content_type(content_type: str) -> str | None:
    return CONTENT_TYPE_SUFFIXES.get(content_type.casefold().split(";", maxsplit=1)[0].strip())
