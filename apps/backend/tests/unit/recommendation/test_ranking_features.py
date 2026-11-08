from dataclasses import replace
from uuid import UUID

import pytest

from aprkb.modules.recommendation.diversifier import MmrDiversifier, frame_tokens, jaccard
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.recommendation.pipeline import RecommendationItem
from aprkb.modules.recommendation.scorers.implementations import IntentScorer, LinguisticScorer
from aprkb.shared.keywords import normalize_token


def item(frame: str, score: float = 1.0, index: int = 1) -> RecommendationItem:
    return RecommendationItem(
        pattern=PatternView(
            pattern_version_id=UUID(int=index),
            status="approved",
            intent_code="report_finding",
            canonical_frame=frame,
            claim_type=None,
            epistemic_strength=None,
            allowed_sections=(),
            allowed_genres=(),
            source_type="authored",
            license_allows_display=True,
            move_code="report",
        ),
        score=score,
        breakdown={"intent": 1.0},
        fallback_tier="generic_genre",
        explanations=(),
    )


@pytest.mark.parametrize(
    "intent,move,expected",
    [
        ("report_finding", None, 1.0),
        (None, "report", 0.6),
        (None, None, None),
        (None, "other", None),
        ("other", "report", None),
    ],
)
def test_intent_scorer_branches(context, intent, move, expected):
    assert (
        IntentScorer(same_move=0.6).score(
            item("Example").pattern, replace(context, intent_code=intent, move_code=move)
        )
        == expected
    )


@pytest.mark.parametrize(
    "word,expected",
    [
        ("SUGGESTS", "suggest"),
        ("suggested", "suggest"),
        ("suggesting", "suggest"),
        ("matches", "match"),
        ("uses", "use"),
        ("is", "is"),
        ("as", "as"),
        ("class", "class"),
        ("analysis", "analysis"),
    ],
)
def test_suffix_normalization(word, expected):
    assert normalize_token(word) == expected


def test_linguistic_normalizes_both_query_and_frame(context):
    scorer = LinguisticScorer()
    assert (
        scorer.score(item("We suggest {topic}.").pattern, replace(context, query="suggests")) == 1
    )
    assert (
        scorer.score(item("We suggested {topic}.").pattern, replace(context, query="suggest")) == 1
    )
    assert scorer.score(item("Example").pattern, replace(context, query="!?")) is None


def test_mmr_reduces_near_duplicates_and_is_deterministic():
    candidates = [
        item("These results suggest {finding}.", 1.0, 1),
        item("These results suggest {other}.", 0.99, 2),
        item("These results strongly suggest {finding}.", 0.98, 3),
        item("Prior research leaves an unresolved gap.", 0.8, 4),
        item("Our method measures the sample.", 0.7, 5),
    ]
    diversifier = MmrDiversifier(lambda_=0.7, max_similarity=0.7)
    result = diversifier.diversify(candidates)[:3]
    assert result[0] == candidates[0]
    assert len(result) == 3
    assert sum(candidate in candidates[:3] for candidate in result) == 1
    assert result == diversifier.diversify(candidates)[:3]


def test_mmr_preserves_input_ties_and_can_underfill():
    candidates = [item("alpha", 1, 1), item("beta", 0.9, 2), item("gamma", 0.9, 3)]
    assert MmrDiversifier(lambda_=1, max_similarity=1).diversify(candidates) == candidates
    duplicates = [item("results {x}", 1, 1), item("results {y}", 0.9, 2)]
    assert MmrDiversifier(lambda_=0.7, max_similarity=0.85).diversify(duplicates) == duplicates[:1]


def test_mmr_slot_punctuation_empty_and_boundaries():
    assert frame_tokens("RESULTS, {topic}!") == frozenset({"results"})
    assert jaccard(frozenset(), frozenset()) == 0
    for lambda_ in (0, 1):
        diversifier = MmrDiversifier(lambda_=lambda_, max_similarity=0)
        assert diversifier.diversify([]) == []
        singleton = [item("{topic}")]
        assert diversifier.diversify(singleton) == singleton
    boundary = [item("alpha beta", 1, 1), item("alpha", 0.9, 2)]
    assert len(MmrDiversifier(lambda_=0.7, max_similarity=0.5).diversify(boundary)) == 2


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
def test_mmr_rejects_invalid_policy_values(value):
    with pytest.raises(ValueError):
        MmrDiversifier(lambda_=value, max_similarity=0.85)
    with pytest.raises(ValueError):
        MmrDiversifier(lambda_=0.7, max_similarity=value)
