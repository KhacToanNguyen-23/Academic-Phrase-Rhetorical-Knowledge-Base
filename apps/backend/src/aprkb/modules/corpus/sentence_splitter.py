"""Shared character-level sentence boundaries for regex and spaCy ingest."""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from enum import StrEnum
from functools import cache

from aprkb.policies.schemas import SentenceRulesPolicy


class BoundaryDecision(StrEnum):
    SPLIT = "split"
    NO_SPLIT = "no_split"
    UNSURE = "unsure"


@dataclass(frozen=True)
class BoundaryCandidate:
    """A possible next-sentence offset and the rule that classified it."""

    offset: int
    decision: BoundaryDecision
    rule: str


@dataclass(frozen=True)
class SentenceSpan:
    text: str
    char_start: int
    char_end: int
    boundary_source: str = "rule:start"


_BOUNDARY = re.compile(r"(?<=[.!?\"'\)\]])\s+|\r?\n[ \t]*\r?\n\s*")
_BLANK_LINE = re.compile(r"\r?\n[ \t]*\r?\n")
_NEXT_WORD = re.compile(r"\w+")
_CLOSERS = "\"')]}\u201d\u2019"
_TOKEN = re.compile(r"([A-Za-z](?:[A-Za-z.]*)\.)$")
_UNSPACED = re.compile(r"(?<=[A-Za-z])\.(?=[A-Z])")
_NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)*\.?\s+\S")


@cache
def _packaged_abbreviations() -> frozenset[str]:
    from aprkb.policies.loader import load_policy_bundle

    return frozenset(value.casefold() for value in load_policy_bundle().abbreviations.abbreviations)


@cache
def _packaged_sentence_rules() -> SentenceRulesPolicy:
    from aprkb.policies.loader import load_policy_bundle

    return load_policy_bundle().sentence_rules


@dataclass(frozen=True)
class _BoundaryContext:
    offset: int
    boundary_start: int
    blank_line: bool = False
    heading_line: bool = False
    unspaced: bool = False


def boundary_candidates(
    text: str, rules: SentenceRulesPolicy | None = None
) -> list[BoundaryCandidate]:
    """Classify every permitted sentence-start position using source characters only."""
    policy = rules or _packaged_sentence_rules()
    candidates: list[BoundaryCandidate] = []
    seen: set[int] = set()
    for context in sorted(_contexts(text, policy), key=lambda item: item.offset):
        if context.offset in seen:
            continue
        seen.add(context.offset)
        if context.blank_line:
            candidates.append(
                BoundaryCandidate(context.offset, BoundaryDecision.SPLIT, "blank_line")
            )
            continue
        if context.heading_line:
            candidates.append(
                BoundaryCandidate(context.offset, BoundaryDecision.SPLIT, "heading_line")
            )
            continue
        if context.unspaced:
            candidates.append(BoundaryCandidate(context.offset, BoundaryDecision.SPLIT, "unspaced"))
            continue
        decision, rule = _classify_context(text, context, policy)
        candidates.append(BoundaryCandidate(context.offset, decision, rule))
    return candidates


def split_sentences(
    text: str,
    *,
    abbreviations: Collection[str] | None = None,
    rules: SentenceRulesPolicy | None = None,
) -> list[SentenceSpan]:
    """Split text with the shared rules and preserve exact source offsets."""
    known = (
        _packaged_abbreviations()
        if abbreviations is None
        else frozenset(value.casefold() for value in abbreviations)
    )
    policy = rules or _packaged_sentence_rules()
    spans: list[SentenceSpan] = []
    start = 0
    source = "rule:start"
    for candidate in boundary_candidates(text, policy):
        if candidate.decision is BoundaryDecision.UNSURE:
            should_split = _resolve_unsure(text, candidate, known, policy)
        else:
            should_split = candidate.decision is BoundaryDecision.SPLIT
        if not should_split:
            continue
        _append_span(spans, text, start, candidate.offset, source)
        start = candidate.offset
        source = f"rule:{candidate.rule}"
    _append_span(spans, text, start, len(text), source)
    return spans


def _contexts(text: str, rules: SentenceRulesPolicy) -> Iterable[_BoundaryContext]:
    for boundary in _BOUNDARY.finditer(text):
        yield _BoundaryContext(
            offset=boundary.end(),
            boundary_start=boundary.start(),
            blank_line=bool(_BLANK_LINE.search(boundary.group())),
        )
    for match in _UNSPACED.finditer(text):
        left_word = re.search(r"[A-Za-z]+$", text[: match.start()])
        if left_word is not None and (
            left_word.group().islower() or left_word.group().casefold().endswith("s")
        ):
            yield _BoundaryContext(
                offset=match.end(), boundary_start=match.start() + 1, unspaced=True
            )
    for line_start, line_end in _line_breaks(text):
        line = text[line_start:line_end].strip()
        if _is_heading_line(line, rules):
            offset = line_end
            while offset < len(text) and text[offset] in "\r\n \t":
                if text[offset] in "\r\n":
                    offset += 1
                    break
                offset += 1
            if offset < len(text):
                yield _BoundaryContext(offset=offset, boundary_start=line_end, heading_line=True)


def _line_breaks(text: str) -> Iterable[tuple[int, int]]:
    start = 0
    for match in re.finditer(r"\r?\n", text):
        yield start, match.start()
        start = match.end()
    if start < len(text):
        yield start, len(text)


def _is_heading_line(line: str, rules: SentenceRulesPolicy) -> bool:
    if not line or len(line) > rules.heading_max_chars:
        return False
    if len(line.split()) > rules.heading_max_words or line[-1:] in ".!?;:":
        return False
    return bool(_NUMBERED_HEADING.match(line))


def _classify_context(
    text: str, context: _BoundaryContext, rules: SentenceRulesPolicy
) -> tuple[BoundaryDecision, str]:
    if _inside_numbered_heading(text, context.boundary_start, rules):
        return BoundaryDecision.NO_SPLIT, "heading_internal"
    if _inside_open_delimiter(text[: context.boundary_start]):
        return BoundaryDecision.NO_SPLIT, "open_bracket"

    end = context.boundary_start
    while end and text[end - 1] in _CLOSERS:
        end -= 1
    punctuation = text[end - 1] if end else ""
    next_start, next_word = _next_word(text, context.offset)
    if punctuation in "!?":
        if _inside_open_quote(text[: context.boundary_start]):
            return BoundaryDecision.NO_SPLIT, "open_quote"
        return (
            (BoundaryDecision.SPLIT, "question_exclamation")
            if next_word and text[next_start].isupper()
            else (BoundaryDecision.NO_SPLIT, "lowercase_continuation")
        )

    token_match = _TOKEN.search(text[:end])
    token = token_match.group(1) if token_match else ""
    normalized = token.casefold()
    next_char = text[next_start] if next_word else ""
    if token and _is_decimal_or_doi(text[:end], token):
        return BoundaryDecision.NO_SPLIT, "decimal_version_url"
    if token and len(normalized) == 2 and next_char.isupper():
        if next_word.casefold() in rules.sentence_starters:
            return BoundaryDecision.UNSURE, "unsure_initial"
        return BoundaryDecision.NO_SPLIT, "initial"
    if token and next_char.isdigit():
        return BoundaryDecision.NO_SPLIT, "abbrev_digit"
    if token and next_char.islower():
        return BoundaryDecision.NO_SPLIT, "lowercase_continuation"

    abbreviations = _packaged_abbreviations()
    is_abbreviation = normalized[:-1] in abbreviations if token else False
    is_unit = normalized[:-1] in rules.unit_tokens if token else False
    if (is_abbreviation or is_unit) and next_char.isupper():
        if next_word.casefold() in rules.sentence_starters:
            return BoundaryDecision.SPLIT, "abbrev_starter"
        return BoundaryDecision.UNSURE, "unsure_abbreviation"
    if token and "." in normalized[:-1]:
        return BoundaryDecision.UNSURE, "unsure_abbreviation"
    if token:
        return BoundaryDecision.SPLIT, "sentence_punctuation"
    return BoundaryDecision.UNSURE, "unsure_punctuation"


def _inside_numbered_heading(text: str, offset: int, rules: SentenceRulesPolicy) -> bool:
    line_start = text.rfind("\n", 0, offset) + 1
    line_end = text.find("\n", offset)
    line = text[line_start:] if line_end == -1 else text[line_start:line_end]
    return _is_heading_line(line.strip(), rules)


def _next_word(text: str, offset: int) -> tuple[int, str]:
    index = offset
    while index < len(text) and text[index] in "\"'\u201c\u2018([":
        index += 1
    match = _NEXT_WORD.match(text, index)
    return (index, match.group()) if match else (index, "")


def _inside_open_delimiter(prefix: str) -> bool:
    stack: list[str] = []
    pairs = {
        ")": "(",
        "]": "[",
    }
    for char in prefix:
        if char in "([":
            stack.append(char)
        elif char in pairs and stack and stack[-1] == pairs[char]:
            stack.pop()
    return bool(stack)


def _inside_open_quote(prefix: str) -> bool:
    return prefix.count('"') % 2 == 1 or prefix.count("'") % 2 == 1


def _is_decimal_or_doi(prefix: str, token: str) -> bool:
    if re.search(r"\b\d+\.\d+(?:\.\d+)*\.$", prefix):
        return True
    return token.casefold() in {"doi."}


def _resolve_unsure(
    text: str,
    candidate: BoundaryCandidate,
    abbreviations: Collection[str],
    rules: SentenceRulesPolicy,
) -> bool:
    boundary_start = candidate.offset
    while boundary_start and text[boundary_start - 1].isspace():
        boundary_start -= 1
    end = boundary_start
    while end and text[end - 1] in _CLOSERS:
        end -= 1
    if not end or text[end - 1] not in ".!?":
        return False
    if text[end - 1] != ".":
        return True
    token_start = end - 1
    while token_start and (text[token_start - 1].isalpha() or text[token_start - 1] == "."):
        token_start -= 1
    token = _TOKEN.search(text, token_start, end)
    if token is None:
        return True
    word = token.group(1).casefold()
    if word.endswith("..."):
        return True
    if word[:-1] in abbreviations:
        return False
    next_start, next_word = _next_word(text, candidate.offset)
    if not next_word:
        return True
    if text[next_start].islower():
        return False
    if word in {"etc."} or "." in word[:-1] or len(word) == 2:
        return text[next_start].isupper() and next_word.casefold() in rules.sentence_starters
    return True


def _append_span(
    spans: list[SentenceSpan], source: str, start: int, end: int, boundary_source: str
) -> None:
    while start < end and source[start].isspace():
        start += 1
    while end > start and source[end - 1].isspace():
        end -= 1
    if start < end:
        spans.append(SentenceSpan(source[start:end], start, end, boundary_source))
