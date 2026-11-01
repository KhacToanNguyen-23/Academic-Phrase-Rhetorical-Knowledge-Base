"""Regex sentence splitting that returns offsets into the original text."""

import re
from collections.abc import Collection
from dataclasses import dataclass
from functools import cache


@dataclass(frozen=True)
class SentenceSpan:
    text: str
    char_start: int
    char_end: int


# A blank line also ends a sentence, so headings and list items stay separate.
_BOUNDARY = re.compile(r"(?<=[.!?])(?:[\"'”’)]*)\s+|\n[ \t]*\n\s*")
_LAST_TOKEN = re.compile(r"(\S+)\.$")
_INITIAL = re.compile(r"^[(\[]?[A-Z]$")


@cache
def _packaged_abbreviations() -> frozenset[str]:
    from aprkb.policies.loader import load_policy_bundle

    return frozenset(load_policy_bundle().abbreviations.abbreviations)


def split_sentences(
    text: str, *, abbreviations: Collection[str] | None = None
) -> list[SentenceSpan]:
    """Split ``text`` into sentences.

    A period does not end a sentence after a listed abbreviation (``e.g.``, ``et al.``),
    after a single capital initial (``J. Smith``), or when the next word starts in lower case.
    """
    known = (
        _packaged_abbreviations()
        if abbreviations is None
        else frozenset(value.casefold() for value in abbreviations)
    )
    spans: list[SentenceSpan] = []
    start = 0
    for boundary in _BOUNDARY.finditer(text):
        if _is_false_boundary(text, start, boundary, known):
            continue
        _append_span(spans, text, start, boundary.start())
        start = boundary.end()
    _append_span(spans, text, start, len(text))
    return spans


def _is_false_boundary(
    text: str, start: int, boundary: re.Match[str], abbreviations: frozenset[str]
) -> bool:
    if text.count("\n", boundary.start(), boundary.end()) >= 2:
        return False  # paragraph breaks always end a sentence
    before = text[start : boundary.start()]
    token_match = _LAST_TOKEN.search(before)
    if token_match is not None:
        token = token_match.group(1).lstrip("([")
        if token.casefold() in abbreviations or _INITIAL.match(token):
            return True
    following = text[boundary.end() : boundary.end() + 1]
    return bool(following) and following.islower()


def _append_span(spans: list[SentenceSpan], source: str, start: int, end: int) -> None:
    while start < end and source[start].isspace():
        start += 1
    while end > start and source[end - 1].isspace():
        end -= 1
    if start < end:
        spans.append(SentenceSpan(source[start:end], start, end))
