"""Rule-based English sentence boundaries with offsets into the original text.

Abbreviations are inherently ambiguous; these conservative scholarly-text rules
avoid requiring an NLP model while keeping source text and provenance intact.
"""

import re
from collections.abc import Collection
from dataclasses import dataclass
from functools import cache


@dataclass(frozen=True)
class SentenceSpan:
    text: str
    char_start: int
    char_end: int


# Match whitespace only: closing punctuation belongs to the preceding sentence.
_BOUNDARY = re.compile(r"(?<=[.!?\"'”’\)\]])\s+|\r?\n[ \t]*\r?\n\s*")
_BLANK_LINE = re.compile(r"\r?\n[ \t]*\r?\n")
_NEXT_WORD = re.compile(r"\w+")
_CLOSERS = "\"'”’)]"
_TOKEN = re.compile(r"([A-Za-z]+(?:\.[A-Za-z]+)*\.)$")
# An initial or acronym may end a sentence too. These common sentence openings
# provide a limited context cue; other capitalized words can be names/entities.
_SENTENCE_STARTERS = frozenset(
    {
        "a",
        "an",
        "the",
        "this",
        "that",
        "these",
        "those",
        "we",
        "they",
        "it",
        "he",
        "she",
        "however",
        "therefore",
        "thus",
        "in",
        "our",
        "results",
        "next",
        "then",
    }
)


@cache
def _packaged_abbreviations() -> frozenset[str]:
    from aprkb.policies.loader import load_policy_bundle

    return frozenset(value.casefold() for value in load_policy_bundle().abbreviations.abbreviations)


def _is_sentence_end(text: str, boundary: re.Match[str], abbreviations: Collection[str]) -> bool:
    if _BLANK_LINE.search(boundary.group()):
        return True
    end = boundary.start()
    while end and text[end - 1] in _CLOSERS:
        end -= 1
    if not end or text[end - 1] not in ".!?":
        return False
    if text[end - 1] != ".":
        return True
    # Restrict the search to the current token to avoid rescanning the article.
    token_start = end - 1
    while token_start and (text[token_start - 1].isalpha() or text[token_start - 1] == "."):
        token_start -= 1
    token = _TOKEN.search(text, token_start, end)
    if token is None:
        return True
    word = token.group(1).casefold()
    if word[:-1] in abbreviations:
        return False
    following_start = boundary.end()
    while following_start < len(text) and text[following_start] in "\"'“‘([":
        following_start += 1
    next_word = _NEXT_WORD.match(text, following_start)
    if next_word is None:
        return True
    if text[following_start].islower():
        return False
    if word in {"etc."} or "." in word[:-1] or len(word) == 2:
        if text[following_start].isupper() and next_word.group().lower() in _SENTENCE_STARTERS:
            return True
        return text[following_start].isupper() and word in {"al.", "etc."}
    return True


def split_sentences(
    text: str, *, abbreviations: Collection[str] | None = None
) -> list[SentenceSpan]:
    """Split text at likely sentence ends, preserving source offsets.

    A period does not end a sentence after a configured scholarly abbreviation or initial.
    """
    known = (
        _packaged_abbreviations()
        if abbreviations is None
        else frozenset(value.casefold() for value in abbreviations)
    )
    spans: list[SentenceSpan] = []
    start = 0
    for boundary in _BOUNDARY.finditer(text):
        if not _is_sentence_end(text, boundary, known):
            continue
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
