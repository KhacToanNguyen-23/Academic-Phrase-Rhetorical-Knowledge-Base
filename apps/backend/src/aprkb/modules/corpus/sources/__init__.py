"""External article sources and their registry."""

from collections.abc import Callable

from aprkb.modules.corpus.sources.base import (
    ArticleSource,
    SourceArticleRef,
    SourcePage,
    suffix_for_content_type,
)
from aprkb.modules.corpus.sources.null_source import NullArticleSource

# TODO(owner, PRD-04): register the HTTP adapter for the chosen article API here.
_SOURCES: dict[str, Callable[[], ArticleSource]] = {"null": NullArticleSource}


def build_article_source(name: str) -> ArticleSource:
    factory = _SOURCES.get(name)
    if factory is None:
        raise ValueError(f"Unknown article source: {name}")
    return factory()


__all__ = [
    "ArticleSource",
    "NullArticleSource",
    "SourceArticleRef",
    "SourcePage",
    "build_article_source",
    "suffix_for_content_type",
]
