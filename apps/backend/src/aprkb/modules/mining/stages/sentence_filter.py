"""Configured sentence filter: inline citations, length bounds, and noise (spec 3.1b)."""

import re

from aprkb.modules.mining.stages.base import MiningItem, MiningStage
from aprkb.nlp.syntax import children_by_head, select_syntax_root
from aprkb.policies.schemas import NoiseFilterSettings, SyntaxFilterSettings

_CITATION = re.compile(
    r"\s*(?:\[\s*\d+(?:\s*,\s*\d+)*\s*\]|\([^()]*\b(?:18|19|20)\d{2}[a-z]?\b[^()]*\))"
)
_CAPTION = re.compile(
    r"^(?:fig(?:ure)?s?\.?|tab(?:le)?s?\.?|algorithm)\s*\d+[a-z]?\s*[.:]", re.IGNORECASE
)
_MATH_SYMBOLS = frozenset("=+−×÷^_{}\\<>≤≥∈∉∀∃∑∏∫∂∇√∞≈≠±·⊂⊆∪∩→←↦‖")


def _is_math_char(char: str) -> bool:
    code = ord(char)
    # Greek letters and Unicode mathematical alphanumerics (e.g. italic 𝑘 in PDF exports).
    return char in _MATH_SYMBOLS or 0x0370 <= code <= 0x03FF or 0x1D400 <= code <= 0x1D7FF


def noise_reason(text: str, section_code: str | None, settings: NoiseFilterSettings) -> str | None:
    """Return why a sentence is noise, or ``None`` when it may be mined."""
    if section_code is not None and section_code in settings.excluded_sections:
        return "excluded_section"
    if text.count("|") >= settings.min_table_pipes:
        return "table_row"
    if _CAPTION.match(text.lstrip()):
        return "caption"
    visible = [char for char in text if not char.isspace()]
    if visible and sum(map(_is_math_char, visible)) / len(visible) > settings.max_math_symbol_ratio:
        return "math"
    tokens = text.split()
    numeric = sum(any(char.isdigit() for char in token) for token in tokens)
    if tokens and numeric / len(tokens) > settings.max_numeric_token_ratio:
        return "numeric"
    return None


class SentenceFilter(MiningStage):
    name = "sentence_filter"
    requirement_id = "FR-07"

    def __init__(
        self,
        *,
        min_words: int,
        max_words: int,
        noise: NoiseFilterSettings | None = None,
        syntax: SyntaxFilterSettings | None = None,
    ) -> None:
        if min_words < 0 or max_words < min_words:
            raise ValueError("sentence word limits must be non-negative and ordered")
        self._min_words = min_words
        self._max_words = max_words
        self._noise = noise
        self._syntax = syntax

    def reject_reason(self, item: MiningItem) -> str | None:
        if self._noise is not None:
            reason = noise_reason(item.text, item.section_code, self._noise)
            if reason is not None:
                return reason
        word_count = len(_CITATION.sub("", item.text).split())
        if not self._min_words <= word_count <= self._max_words:
            return "length"
        if (
            item.tokens is not None
            and self._syntax is not None
            and self._syntax.require_finite_verb
        ):
            content_tokens = [token for token in item.tokens if not token.is_space]
            has_finite = any(
                token.tag == "MD"
                or (token.pos in {"VERB", "AUX"} and _has_morph(token.morph, "VerbForm=Fin"))
                for token in content_tokens
            )
            root = select_syntax_root(item.tokens)
            if not has_finite and not (self._syntax.allow_imperatives and self.is_imperative(item)):
                return "no_finite_verb"
            if root is None or root.token.pos not in {"VERB", "AUX"}:
                return "root_not_verbal"
        return None

    def is_imperative(self, item: MiningItem) -> bool:
        """Recognize a bare imperative ROOT with a direct complement."""
        if item.tokens is None:
            return False
        selection = select_syntax_root(item.tokens)
        if selection is None:
            return False
        root = selection.token
        if root.pos != "VERB" or root.tag != "VB":
            return False
        children = children_by_head(item.tokens)
        direct = [item.tokens[index] for index in children[root.i]]
        if any(token.dep in {"nsubj", "nsubjpass"} for token in direct):
            return False
        if not any(token.dep in {"dobj", "ccomp", "xcomp", "attr", "prep"} for token in direct):
            return False

        content = [token for token in item.tokens if not token.is_space and token.pos != "PUNCT"]
        if not content:
            return False
        if content[0].i == root.i:
            return True
        if len(content) < 2 or content[1].i != root.i:
            return False
        lead = content[0]
        comma = next(
            (token for token in item.tokens if token.pos == "PUNCT" and token.start >= lead.end),
            None,
        )
        return bool(
            len(item.text[lead.start : lead.end]) <= 12
            and lead.pos in {"ADV", "INTJ", "PART"}
            and comma is not None
            and item.text[lead.end : comma.start].strip() == ""
            and item.text[comma.end : root.start].strip() == ""
            and item.text[comma.start : comma.end] == ","
        )

    def accepted_as_imperative(self, item: MiningItem) -> bool:
        """Return true only when the imperative branch is what lets the item pass."""
        if not self._syntax or not self._syntax.allow_imperatives or item.tokens is None:
            return False
        has_finite = any(
            token.tag == "MD"
            or (token.pos in {"VERB", "AUX"} and _has_morph(token.morph, "VerbForm=Fin"))
            for token in item.tokens
            if not token.is_space
        )
        return not has_finite and self.is_imperative(item) and self.reject_reason(item) is None

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        return [item for item in batch if self.reject_reason(item) is None]


def _has_morph(morph: str, feature: str) -> bool:
    return feature in morph.split("|")
