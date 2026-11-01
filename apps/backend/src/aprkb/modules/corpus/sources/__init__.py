"""External article sources and their registry."""

from aprkb.modules.corpus.sources.base import (
    ArticleSource,
    ImportOptions,
    InvalidContentError,
    SourceArticleRef,
    SourcePage,
    suffix_for_content_type,
)
from aprkb.modules.corpus.sources.null_source import NullArticleSource
from aprkb.modules.corpus.sources.slr_source import SlrRepositorySource


def _build_slr_source() -> ArticleSource:
    from aprkb.core.config import settings

    if settings.slr_api_key is None:
        raise ValueError("SLR_API_KEY is required when ARTICLE_SOURCE=slr")
    return SlrRepositorySource()


_SOURCES = {"null": NullArticleSource, "slr": _build_slr_source}


def build_article_source(name: str) -> ArticleSource:
    factory = _SOURCES.get(name)
    if factory is None:
        raise ValueError(f"Unknown article source: {name}")
    return factory()


__all__ = [
    "ArticleSource",
    "ImportOptions",
    "InvalidContentError",
    "NullArticleSource",
    "SourceArticleRef",
    "SourcePage",
    "build_article_source",
    "suffix_for_content_type",
]
