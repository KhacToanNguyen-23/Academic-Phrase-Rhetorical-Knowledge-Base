"""Pure recommendation orchestration over preloaded pattern views."""

from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.diversifier import Diversifier, PassThroughDiversifier
from aprkb.modules.recommendation.fallback import FallbackTierLoader
from aprkb.modules.recommendation.gates.base import HardGate
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.recommendation.scorers import Scorer, aggregate_scores


class _TierLoader(Protocol):
    tiers: tuple[str, ...]

    def load(self, tier: str, context: RecommendationContext) -> tuple[PatternView, ...]: ...


@dataclass(frozen=True)
class RecommendationItem:
    pattern: PatternView
    score: float
    breakdown: dict[str, float | None]
    fallback_tier: str
    explanations: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationResult:
    items: tuple[RecommendationItem, ...]
    excluded: dict[str, int]


class RecommendationPipeline:
    def __init__(
        self,
        *,
        gates: list[HardGate],
        scorers: list[Scorer],
        weights: dict[str, float],
        tier_loader: FallbackTierLoader | _TierLoader,
        diversifier: Diversifier[RecommendationItem] | None = None,
    ) -> None:
        self._gates = tuple(gates)
        self._scorers = tuple(scorers)
        self._weights = dict(weights)
        self._tier_loader = tier_loader
        self._diversifier = diversifier or PassThroughDiversifier()

    def recommend(self, context: RecommendationContext) -> RecommendationResult:
        accepted: list[RecommendationItem] = []
        excluded: Counter[str] = Counter()
        seen: set[object] = set()
        for tier in self._tier_loader.tiers:
            for pattern in self._tier_loader.load(tier, context):
                if pattern.pattern_version_id in seen:
                    continue
                seen.add(pattern.pattern_version_id)
                failed_gate = next(
                    (gate for gate in self._gates if not gate.check(pattern, context).passed),
                    None,
                )
                if failed_gate is not None:
                    excluded[failed_gate.code] += 1
                    continue
                scores = {scorer.key: scorer.score(pattern, context) for scorer in self._scorers}
                score, breakdown = aggregate_scores(scores=scores, weights=self._weights)
                accepted.append(
                    RecommendationItem(
                        pattern=pattern,
                        score=score,
                        breakdown=breakdown,
                        fallback_tier=tier,
                        explanations=(f"Intent match: {context.intent_code}",),
                    )
                )
            if len(accepted) >= context.limit:
                break
        accepted.sort(key=lambda item: -item.score)
        diversified = self._diversifier.diversify(accepted)
        return RecommendationResult(
            items=tuple(diversified[: context.limit]), excluded=dict(excluded)
        )
