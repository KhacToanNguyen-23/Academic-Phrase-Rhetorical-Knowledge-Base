"""Human-readable recommendation score explanations."""

from aprkb.modules.recommendation.schemas import ExplanationDetail
from aprkb.modules.recommendation.scorers.aggregator import effective_weights
from aprkb.policies.evidence import EvidencePolicy

CRITERION_LABELS = {
    "intent": "Intent",
    "discipline": "Discipline",
    "journal_genre": "Journal and genre",
    "evidence": "Evidence",
    "linguistic": "Keyword match",
    "provenance": "Provenance",
}


def score_explanations(
    breakdown: dict[str, float | None],
    *,
    claim_type: str | None,
    strength: str | None,
    evidence_level: str | None,
    evidence_policy: EvidencePolicy,
) -> list[str]:
    """Describe each measured score using its actual value and evidence ceiling."""
    explanations = [
        f"{CRITERION_LABELS[key]}: {value:.3f}"
        if value is not None
        else f"{CRITERION_LABELS[key]}: not available"
        for key, value in breakdown.items()
    ]
    if evidence_level is not None:
        try:
            maximum = evidence_policy.max_strength(claim_type or "", evidence_level)
        except ValueError:
            maximum = "not available"
        explanations.append(
            f"Evidence strength: {strength or 'Not labelled'}; maximum allowed: {maximum}"
        )
    return explanations


def explanation_details(
    breakdown: dict[str, float | None], *, weights: dict[str, float]
) -> list[ExplanationDetail]:
    normalized = effective_weights(breakdown=breakdown, weights=weights)
    return [
        ExplanationDetail(
            criterion=key,
            value=value if normalized[key] > 0 else None,
            weight=normalized[key],
            available=value is not None and normalized[key] > 0,
        )
        for key, value in breakdown.items()
    ]
