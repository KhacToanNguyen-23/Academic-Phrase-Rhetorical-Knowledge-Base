"""Weighted score aggregation with missing and disabled scorer handling."""

from math import isfinite


def effective_weights(
    *, breakdown: dict[str, float | None], weights: dict[str, float]
) -> dict[str, float]:
    """Normalize configured weights over the available, enabled criteria of one item."""
    active = {
        key: weights[key]
        for key, value in breakdown.items()
        if value is not None and weights[key] > 0
    }
    total = sum(active.values())
    if total <= 0:
        raise ValueError("at least one available scorer must have positive weight")
    return {key: weights[key] / total if key in active else 0.0 for key in breakdown}


def aggregate_scores(
    *, scores: dict[str, float | None], weights: dict[str, float]
) -> tuple[float, dict[str, float | None]]:
    """Return the weighted total and raw-score breakdown (disabled/missing scores are null)."""
    if set(scores) != set(weights):
        raise ValueError("scores and weights must contain the same scorer keys")
    active: dict[str, float] = {}
    breakdown: dict[str, float | None] = {}
    for key, score in scores.items():
        weight = weights[key]
        if not isfinite(weight) or weight < 0:
            raise ValueError(f"weight for {key} must be finite and non-negative")
        if score is not None and (not isfinite(score) or score < 0 or score > 1):
            raise ValueError(f"score for {key} must be between 0 and 1")
        if score is None or weight == 0:
            breakdown[key] = None
        else:
            active[key] = score
            breakdown[key] = score
    normalized = effective_weights(breakdown=breakdown, weights=weights)
    total = sum(active[key] * normalized[key] for key in active)
    return total, breakdown
