"""Lexical diversification over eligible, sorted recommendations."""

import re
from collections.abc import Sequence
from math import isfinite
from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from aprkb.modules.recommendation.pipeline import RecommendationItem

T = TypeVar("T")


class Diversifier(Protocol[T]):
    def diversify(self, items: Sequence[T]) -> list[T]: ...


class PassThroughDiversifier:
    def diversify(self, items: Sequence[T]) -> list[T]:
        # Useful when lexical diversity is explicitly disabled by the caller.
        return list(items)


def frame_tokens(frame: str) -> frozenset[str]:
    """Ignore slot names; diversity is lexical and does not stem words."""
    without_slots = re.sub(r"\{[^{}]*\}", " ", frame)
    return frozenset(re.findall(r"[^\W_]+", without_slots.casefold(), re.UNICODE))


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


class MmrDiversifier:
    """Greedy MMR over sorted candidates, with a hard similarity cap.

    Ties preserve input order. The first (highest-ranked) candidate is retained.
    Exceeding the cap removes a candidate; the pipeline does not refill tiers.
    """

    def __init__(self, *, lambda_: float, max_similarity: float) -> None:
        if any(not isfinite(value) or not 0 <= value <= 1 for value in (lambda_, max_similarity)):
            raise ValueError("diversity parameters must be finite values in [0, 1]")
        self._lambda = lambda_
        self._cap = max_similarity

    def diversify(self, items: Sequence["RecommendationItem"]) -> list["RecommendationItem"]:
        if not items:
            return []
        tokens = [frame_tokens(item.pattern.canonical_frame) for item in items]
        frames = [" ".join(item.pattern.canonical_frame.casefold().split()) for item in items]
        selected = [0]
        remaining = list(range(1, len(items)))
        similarities = [0.0] * len(items)
        while remaining:
            last = selected[-1]
            for index in remaining:
                similarity = jaccard(tokens[index], tokens[last])
                if not tokens[index] and not tokens[last] and frames[index] == frames[last]:
                    similarity = 1.0
                similarities[index] = max(similarities[index], similarity)
            remaining = [index for index in remaining if similarities[index] <= self._cap]
            if not remaining:
                break
            # max returns the first tie; remaining follows the pipeline's stable sort.
            best = max(
                remaining,
                key=lambda index: (
                    self._lambda * items[index].score - (1 - self._lambda) * similarities[index]
                ),
            )
            selected.append(best)
            remaining.remove(best)
        return [items[index] for index in selected]
