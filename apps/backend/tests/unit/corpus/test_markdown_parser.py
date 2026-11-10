"""Unit tests for Markdown article parsing."""

from aprkb.modules.corpus.parsers.markdown_parser import MarkdownParser
from aprkb.modules.corpus.sentence_splitter import split_sentences

_SOURCE = b"""---
title: Fixture
---
# Introduction

Prior work has **largely** examined [retrieval](https://example.org) in
isolation. This study extends `that` view.

```python
print("code is dropped")
```

## Results

- The *proposed* method improves accuracy.
| table | row |
"""


def test_markdown_headings_become_sections_with_clean_prose() -> None:
    parser = MarkdownParser()

    document = parser.parse(_SOURCE)

    assert parser.supports("text/markdown; charset=utf-8")
    assert [section.heading for section in document.sections] == ["Introduction", "Results"]
    assert document.sections[0].text == (
        "Prior work has largely examined retrieval in isolation. This study extends that view."
    )
    assert document.sections[1].text == "The proposed method improves accuracy."
    assert "print" not in document.raw_text
    assert "table" not in document.raw_text


def test_markdown_section_offsets_point_into_raw_text() -> None:
    document = MarkdownParser().parse(_SOURCE)

    for section in document.sections:
        start = section.char_start
        assert document.raw_text[start : start + len(section.text)] == section.text
        for span in split_sentences(section.text):
            assert document.raw_text[start + span.char_start : start + span.char_end] == span.text


def test_markdown_without_headings_keeps_a_single_untitled_section() -> None:
    document = MarkdownParser().parse(b"Plain prose only.\n\nSecond paragraph.")

    assert len(document.sections) == 1
    assert document.sections[0].heading is None
    assert document.raw_text == "Plain prose only.\n\nSecond paragraph."


def test_markdown_splits_merged_parent_child_heading() -> None:
    document = MarkdownParser().parse(
        b"## 2 BACKGROUND AND MODEL 2.1 Stochastic Gradient Descent\n\nDetails follow."
    )

    assert [section.heading for section in document.sections] == [
        "2 BACKGROUND AND MODEL",
        "2.1 Stochastic Gradient Descent",
    ]
    assert document.sections[0].text == ""
    assert document.sections[1].text == "Details follow."


def test_markdown_splits_plausible_sibling_but_not_arbitrary_heading_numbers() -> None:
    sibling = MarkdownParser().parse(b"## 3.1 First 3.2 Second\n\nBody.")
    lowercase_title = MarkdownParser().parse(b"## 2 Model 2.1 problem definition\n\nBody.")
    arbitrary = MarkdownParser().parse(b"## 2 Model 2024 Results\n\nBody.")

    assert [section.heading for section in sibling.sections] == ["3.1 First", "3.2 Second"]
    assert [section.heading for section in lowercase_title.sections] == [
        "2 Model",
        "2.1 problem definition",
    ]
    assert [section.heading for section in arbitrary.sections] == ["2 Model 2024 Results"]


def test_markdown_does_not_guess_a_title_for_number_only_heading() -> None:
    document = MarkdownParser().parse(b"## 1.3\n\nDetails follow.")

    assert [section.heading for section in document.sections] == ["1.3"]
