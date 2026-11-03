"""Pure fallback candidate source driven by the versioned tier policy."""

from collections.abc import Mapping, Sequence

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.pattern_view import PatternView


def choose_fallback_tier(
    tiers: Sequence[str],
    *,
    journal_genre_verified: bool = False,
    similar_journal_fingerprint_verified: bool = False,
    subfield_genre_verified: bool = False,
    field_genre_verified: bool = False,
) -> str | None:
    """Choose the first tier supported by verified journal/fingerprint/classification data.

    TODO(owner, FR-07.6): supply these signals after Offline publishes them.
    The current read side has no such signals and therefore uses generic_genre.
    """
    supported = {
        "journal_genre": journal_genre_verified,
        "similar_journal_genre": similar_journal_fingerprint_verified,
        "subfield_genre": subfield_genre_verified,
        "field_genre": field_genre_verified,
        "generic_genre": True,
    }
    return next((tier for tier in tiers if supported.get(tier, False)), None)


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
