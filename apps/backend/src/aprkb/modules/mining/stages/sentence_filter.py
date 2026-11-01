"""Configured sentence filter: inline citations, length bounds, and noise (spec 3.1b)."""

import re

from aprkb.modules.mining.stages.base import MiningItem, MiningStage
from aprkb.policies.schemas import NoiseFilterSettings

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
        self, *, min_words: int, max_words: int, noise: NoiseFilterSettings | None = None
    ) -> None:
        if min_words < 0 or max_words < min_words:
            raise ValueError("sentence word limits must be non-negative and ordered")
        self._min_words = min_words
        self._max_words = max_words
        self._noise = noise

    def reject_reason(self, item: MiningItem) -> str | None:
        if self._noise is not None:
            reason = noise_reason(item.text, item.section_code, self._noise)
            if reason is not None:
                return reason
        word_count = len(_CITATION.sub("", item.text).split())
        if not self._min_words <= word_count <= self._max_words:
            return "length"
        return None

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        return [
            MiningItem(
                text=_CITATION.sub("", item.text).strip(),
                source_sentence_ids=list(item.source_sentence_ids),
                section_code=item.section_code,
            )
            for item in batch
            if self.reject_reason(item) is None
        ]
