"""Configured sentence-length and inline-citation filter."""

import re

from aprkb.modules.mining.stages.base import MiningItem, MiningStage

_CITATION = re.compile(
    r"\s*(?:\[\s*\d+(?:\s*,\s*\d+)*\s*\]|\([^()]*\b(?:18|19|20)\d{2}[a-z]?\b[^()]*\))"
)


class SentenceFilter(MiningStage):
    name = "sentence_filter"
    requirement_id = "FR-07"

    def __init__(self, *, min_words: int, max_words: int) -> None:
        if min_words < 0 or max_words < min_words:
            raise ValueError("sentence word limits must be non-negative and ordered")
        self._min_words = min_words
        self._max_words = max_words

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        results: list[MiningItem] = []
        for item in batch:
            text = _CITATION.sub("", item.text).strip()
            word_count = len(text.split())
            if self._min_words <= word_count <= self._max_words:
                results.append(
                    MiningItem(text=text, source_sentence_ids=list(item.source_sentence_ids))
                )
        return results
