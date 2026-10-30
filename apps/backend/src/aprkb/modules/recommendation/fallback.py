"""Pure fallback candidate source driven by the versioned tier policy."""

from collections.abc import Mapping, Sequence

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.pattern_view import PatternView


class FallbackTierLoader:
    def __init__(
        self,
        *,
        tiers: Sequence[str],
        by_tier: Mapping[str, Sequence[PatternView]],
    ) -> None:
        self.tiers = tuple(tiers)
        self._by_tier = {tier: tuple(items) for tier, items in by_tier.items()}

    def load(self, tier: str, context: RecommendationContext) -> tuple[PatternView, ...]:
        del context
        return self._by_tier.get(tier, ())
