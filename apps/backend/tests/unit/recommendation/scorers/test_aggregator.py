import pytest

from aprkb.modules.recommendation.explanations import explanation_details, score_explanations
from aprkb.modules.recommendation.scorers.aggregator import aggregate_scores


@pytest.mark.parametrize(
    "disabled", ["intent", "discipline", "journal_genre", "evidence", "linguistic", "provenance"]
)
def test_ablation_renormalizes_effective_weights(disabled, policy_bundle):
    scores = {
        "intent": 1.0,
        "discipline": 0.4,
        "journal_genre": 0.6,
        "evidence": 0.5,
        "linguistic": 0.0,
        "provenance": 0.7,
    }
    weights = dict(policy_bundle.ranking_weights.weights)
    weights[disabled] = 0
    total, breakdown = aggregate_scores(scores=scores, weights=weights)
    details = explanation_details(breakdown, weights=weights)
    assert breakdown[disabled] is None
    disabled_detail = next(detail for detail in details if detail.criterion == disabled)
    assert disabled_detail.value is None
    assert disabled_detail.weight == 0
    assert disabled_detail.available is False
    assert sum(detail.weight for detail in details if detail.available) == pytest.approx(1)
    assert sum((detail.value or 0) * detail.weight for detail in details) == pytest.approx(total)
    if disabled != "linguistic":
        assert next(detail for detail in details if detail.criterion == "linguistic").available


def test_details_exclude_missing_signals_and_keep_zero_scores_available():
    total, breakdown = aggregate_scores(
        scores={"intent": 1.0, "discipline": None, "linguistic": 0.0},
        weights={"intent": 0.1, "discipline": 0.7, "linguistic": 0.2},
    )
    details = {
        detail.criterion: detail
        for detail in explanation_details(
            breakdown, weights={"intent": 0.1, "discipline": 0.7, "linguistic": 0.2}
        )
    }
    assert details["intent"].weight == pytest.approx(1 / 3)
    assert details["linguistic"].weight == pytest.approx(2 / 3)
    assert details["linguistic"].value == 0.0
    assert details["linguistic"].available is True
    assert details["discipline"].value is None
    assert details["discipline"].weight == 0
    assert details["discipline"].available is False
    assert total == pytest.approx(1 / 3)


def test_moved_explanations_preserve_legacy_strings(evidence_policy):
    assert score_explanations(
        {"provenance": 0.7, "linguistic": None},
        claim_type=None,
        strength=None,
        evidence_level=None,
        evidence_policy=evidence_policy,
    ) == ["Provenance: 0.700", "Keyword match: not available"]
