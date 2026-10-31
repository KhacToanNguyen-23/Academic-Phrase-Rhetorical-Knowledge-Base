"""Unit tests for the external article source registry."""

import pytest

from aprkb.modules.corpus.sentence_splitter import split_sentences
from aprkb.modules.corpus.sources import (
    NullArticleSource,
    build_article_source,
    suffix_for_content_type,
)


@pytest.mark.asyncio
async def test_null_source_is_the_default_and_lists_nothing() -> None:
    source = build_article_source("null")

    page = await source.list_articles(cursor=None, limit=10)

    assert isinstance(source, NullArticleSource)
    assert page.articles == ()
    assert page.next_cursor is None


def test_unknown_source_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_article_source("not-registered")


def test_content_types_map_to_parser_suffixes() -> None:
    assert suffix_for_content_type("application/pdf") == ".pdf"
    assert suffix_for_content_type("text/markdown; charset=utf-8") == ".md"
    assert suffix_for_content_type("text/html") is None


def test_blank_line_ends_a_sentence_without_punctuation() -> None:
    spans = split_sentences("Heading without a period\n\nBody sentence.")

    assert [span.text for span in spans] == ["Heading without a period", "Body sentence."]
