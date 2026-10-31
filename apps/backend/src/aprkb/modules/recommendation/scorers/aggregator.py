"""Weighted score aggregation with missing and disabled scorer handling."""

from math import isfinite


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
    total_weight = sum(weights[key] for key in active)
    if total_weight <= 0:
        raise ValueError("at least one available scorer must have positive weight")
    total = sum(active[key] * weights[key] for key in active) / total_weight
    return total, breakdown
