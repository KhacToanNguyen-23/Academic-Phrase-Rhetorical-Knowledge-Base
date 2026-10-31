"""Regex sentence splitting that returns offsets into the original text."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SentenceSpan:
    text: str
    char_start: int
    char_end: int


# A blank line also ends a sentence, so headings and list items stay separate.
_BOUNDARY = re.compile(r"(?<=[.!?])(?:[\"'”’)]*)\s+|\n[ \t]*\n\s*")


def split_sentences(text: str) -> list[SentenceSpan]:
    spans: list[SentenceSpan] = []
    start = 0
    for boundary in _BOUNDARY.finditer(text):
        _append_span(spans, text, start, boundary.start())
        start = boundary.end()
    _append_span(spans, text, start, len(text))
    return spans


def _append_span(spans: list[SentenceSpan], source: str, start: int, end: int) -> None:
    while start < end and source[start].isspace():
        start += 1
    while end > start and source[end - 1].isspace():
        end -= 1
    if start < end:
        spans.append(SentenceSpan(source[start:end], start, end))
