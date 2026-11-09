"""Seeded invariant and metamorphic checks supplement the golden examples."""

import random
from copy import deepcopy

import pytest

from aprkb.modules.recommendation.diversifier import MmrDiversifier
from aprkb.modules.recommendation.explanations import explanation_details
from aprkb.modules.recommendation.scorers.aggregator import aggregate_scores
from tests.unit.recommendation.test_ranking_features import item


@pytest.mark.parametrize("seed", range(20))
def test_mmr_invariants_over_generated_frames(seed):
    rng = random.Random(20261106 + seed)
    words = ["suggest", "results", "method", "prior", "gap", "kết", "study"]
    candidates = [
        item(
            " ".join(rng.choices(words, k=rng.randrange(8))) + f" {{slot_{index}}}.",
            rng.random(),
            index + 1,
        )
        for index in range(rng.randrange(1, 35))
    ]
    candidates.sort(key=lambda candidate: -candidate.score)
    before = deepcopy(tuple(candidates))
    for lambda_ in (0, 0.3, 0.7, 1):
        for cap in (0, 0.5, 0.85, 1):
            diversifier = MmrDiversifier(lambda_=lambda_, max_similarity=cap)
            actual = diversifier.diversify(candidates)
            assert actual == diversifier.diversify(candidates)
            assert actual[0] == candidates[0]
            ids = [candidate.pattern.pattern_version_id for candidate in actual]
            assert len(ids) == len(set(ids))
            assert all(candidate in before for candidate in actual)
            assert tuple(candidates) == before
            if lambda_ == cap == 1:
                assert actual == candidates


@pytest.mark.parametrize("seed", range(20))
def test_aggregate_invariants_and_weight_scaling(seed):
    rng = random.Random(20261106 + seed)
    keys = ["intent", "discipline", "journal_genre", "evidence", "linguistic", "provenance"]
    for _ in range(25):
        scores = {key: rng.choice([None, 0.0, rng.random()]) for key in keys}
        weights = {key: rng.choice([0.0, rng.random()]) for key in keys}
        scores["intent"], weights["intent"] = rng.random(), 0.1
        original_scores, original_weights = dict(scores), dict(weights)
        total, breakdown = aggregate_scores(scores=scores, weights=weights)
        details = explanation_details(breakdown, weights=weights)
        active = [scores[key] for key in keys if scores[key] is not None and weights[key] > 0]
        assert min(active) <= total + 1e-12
        assert total <= max(active) + 1e-12
        assert sum(detail.weight for detail in details if detail.available) == pytest.approx(1)
        assert sum((detail.value or 0) * detail.weight for detail in details) == pytest.approx(
            total
        )
        assert all(detail.weight == 0 for detail in details if not detail.available)
        factor = 10 ** rng.uniform(-4, 4)
        scaled, scaled_breakdown = aggregate_scores(
            scores=scores, weights={key: value * factor for key, value in weights.items()}
        )
        assert scaled == pytest.approx(total)
        assert scaled_breakdown == breakdown
        assert scores == original_scores
        assert weights == original_weights
