"""Additional requirement, decision-table and boundary coverage for Group 1."""

from dataclasses import replace
from uuid import UUID

import pytest
from pydantic import ValidationError

from aprkb.modules.discipline.null_source import NullDisciplineSource
from aprkb.modules.recommendation.diversifier import MmrDiversifier, frame_tokens, jaccard
from aprkb.modules.recommendation.explanations import CRITERION_LABELS, explanation_details
from aprkb.modules.recommendation.gates.approval import ApprovalGate
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.recommendation.pipeline import RecommendationPipeline
from aprkb.modules.recommendation.schemas import (
    ExplanationDetail,
    FallbackTraceEntry,
    RecommendationRequest,
    RecommendationResponse,
)
from aprkb.modules.recommendation.scorers import build_scorers
from aprkb.modules.recommendation.scorers.aggregator import aggregate_scores
from aprkb.modules.recommendation.scorers.implementations import IntentScorer, LinguisticScorer
from aprkb.policies.schemas import DiversityPolicy, RankingWeightsPolicy
from aprkb.shared.keywords import keyword_tokens


def view(index=1, frame="alpha beta", **changes):
    data = dict(
        pattern_version_id=UUID(int=index),
        status="approved",
        intent_code="report_finding",
        move_code="report",
        canonical_frame=frame,
        claim_type=None,
        epistemic_strength=None,
        allowed_sections=(),
        allowed_genres=(),
        source_type="authored",
        license_allows_display=True,
    )
    data.update(changes)
    return PatternView(**data)


class Loader:
    def __init__(self, tiers):
        self.tiers = tuple(tiers)
        self.rows = tiers
        self.calls = []

    def load(self, tier, context):
        self.calls.append(tier)
        return tuple(self.rows[tier])


class Scores:
    key = "fixture"

    def __init__(self, values):
        self.values = values
        self.calls = []

    def score(self, pattern, context):
        self.calls.append(pattern.pattern_version_id)
        return self.values[pattern.pattern_version_id.int]


def pipeline(loader, values, diversifier=None):
    scorer = Scores(values)
    engine = RecommendationPipeline(
        gates=[ApprovalGate()],
        scorers=[scorer],
        weights={"fixture": 1},
        tier_loader=loader,
        diversifier=diversifier,
    )
    return engine, scorer


@pytest.mark.parametrize(
    "intent,move,pattern_move,expected",
    [
        ("report_finding", "other", "report", 1.0),
        ("wrong", "report", "report", None),
        (None, "report", None, None),
        (None, None, "report", None),
    ],
    ids=["intent-over-move", "wrong-intent-no-rescue", "missing-pattern-move", "missing-context"],
)
def test_APRKB_G1_TC_001_intent_precedence_and_missing_data(
    context, intent, move, pattern_move, expected
):
    """Task 1.1: explicit intent has priority and incomplete move data is unavailable."""
    assert (
        IntentScorer(same_move=0.6).score(
            view(move_code=pattern_move), replace(context, intent_code=intent, move_code=move)
        )
        == expected
    )


@pytest.mark.parametrize("same_move", [0.0, 1.0], ids=["zero", "one"])
def test_APRKB_G1_TC_002_same_move_score_boundaries(context, same_move):
    assert (
        IntentScorer(same_move=same_move).score(
            view(), replace(context, intent_code=None, move_code="report")
        )
        == same_move
    )


def test_APRKB_G1_TC_003_registry_policy_and_labels_agree(policy_bundle, evidence_policy):
    scorers = build_scorers(
        discipline_source=NullDisciplineSource(),
        evidence_policy=evidence_policy,
        ranking_policy=policy_bundle.ranking_weights,
    )
    keys = [scorer.key for scorer in scorers]
    assert len(keys) == len(set(keys))
    assert set(keys) == set(policy_bundle.ranking_weights.weights) == set(CRITERION_LABELS)
    assert policy_bundle.ranking_weights.weights["intent"] > 0


@pytest.mark.parametrize("weights", [{}, {"intent": 1, "extra": 0}])
def test_APRKB_G1_TC_004_aggregator_rejects_key_mismatch(weights):
    with pytest.raises(ValueError, match="same scorer keys"):
        aggregate_scores(scores={"intent": 1}, weights=weights)


@pytest.mark.parametrize("weight", [-0.01, float("nan"), float("inf"), -float("inf")])
def test_APRKB_G1_TC_005_aggregator_rejects_invalid_weights(weight):
    with pytest.raises(ValueError, match="finite and non-negative"):
        aggregate_scores(scores={"intent": 1}, weights={"intent": weight})


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan"), float("inf"), -float("inf")])
def test_APRKB_G1_TC_006_aggregator_rejects_invalid_scores(score):
    with pytest.raises(ValueError, match="between 0 and 1"):
        aggregate_scores(scores={"intent": score}, weights={"intent": 1})


@pytest.mark.parametrize(
    "scores,weights", [({}, {}), ({"intent": None}, {"intent": 1}), ({"intent": 1}, {"intent": 0})]
)
def test_APRKB_G1_TC_007_aggregator_has_no_fabricated_fallback_score(scores, weights):
    with pytest.raises(ValueError, match="positive weight"):
        aggregate_scores(scores=scores, weights=weights)


def test_APRKB_G1_TC_008_score_and_effective_weight_closed_form():
    total, breakdown = aggregate_scores(
        scores={"intent": 0.6, "linguistic": 0.2, "discipline": None, "provenance": 1},
        weights={"intent": 0.1, "linguistic": 0.3, "discipline": 0.6, "provenance": 0},
    )
    details = {
        d.criterion: d
        for d in explanation_details(
            breakdown,
            weights={"intent": 0.1, "linguistic": 0.3, "discipline": 0.6, "provenance": 0},
        )
    }
    assert total == pytest.approx(0.3)
    assert details["intent"].weight == pytest.approx(0.25)
    assert details["linguistic"].weight == pytest.approx(0.75)
    assert details["discipline"].weight == details["provenance"].weight == 0
    assert sum(d.weight for d in details.values()) == pytest.approx(1)


def test_APRKB_G1_TC_009_sort_uses_tier_then_casefold_then_version(context):
    primary = [view(3, "ALPHA"), view(2, "alpha"), view(1, "Zulu")]
    later = [view(4, "aardvark")]
    loader = Loader({"journal_genre": primary, "generic_genre": later})
    engine, _ = pipeline(loader, {1: 0.8, 2: 0.8, 3: 0.8, 4: 0.8})
    result = engine.recommend(replace(context, limit=10))
    assert [item.pattern.pattern_version_id.int for item in result.items] == [2, 3, 1, 4]


def test_APRKB_G1_TC_010_gate_and_sort_precede_diversification(context):
    class Spy:
        def diversify(self, items):
            assert [item.pattern.pattern_version_id.int for item in items] == [2, 1]
            assert all(item.pattern.status == "approved" for item in items)
            return list(items)

    loader = Loader({"generic_genre": [view(1), view(3, status="draft"), view(2)]})
    engine, scorer = pipeline(loader, {1: 0.2, 2: 0.9, 3: 1}, Spy())
    result = engine.recommend(context)
    assert UUID(int=3) not in scorer.calls
    assert result.excluded == {"GATE_APPROVAL": 1}
    assert result.tiers_tried == (("generic_genre", 2),)


def test_APRKB_G1_TC_011_trace_deduplicates_across_and_within_tiers(context):
    shared = view(1)
    loader = Loader(
        {
            "journal_genre": [shared, shared],
            "generic_genre": [shared, view(2, status="draft"), view(3)],
        }
    )
    engine, scorer = pipeline(loader, {1: 0.4, 2: 1, 3: 0.7})
    result = engine.recommend(replace(context, limit=3))
    assert result.tiers_tried == (("journal_genre", 1), ("generic_genre", 1))
    assert scorer.calls == [UUID(int=1), UUID(int=3)]
    assert [item.fallback_tier for item in result.items] == ["generic_genre", "journal_genre"]


def test_APRKB_G1_TC_012_pipeline_five_candidates_top_three(context):
    frames = [
        "These results suggest {finding}.",
        "These results suggest {other}.",
        "These results strongly suggest {finding}.",
        "Prior research leaves an unresolved gap.",
        "Our method measures the sample.",
    ]
    rows = [view(i + 1, frame) for i, frame in enumerate(frames)]
    loader = Loader({"generic_genre": list(reversed(rows))})
    engine, _ = pipeline(
        loader,
        dict(enumerate([1, 0.99, 0.98, 0.8, 0.7], 1)),
        MmrDiversifier(lambda_=0.7, max_similarity=0.7),
    )
    result = engine.recommend(replace(context, limit=3))
    assert len(result.items) == 3
    assert result.items[0].pattern == rows[0]
    assert sum(item.pattern in rows[:3] for item in result.items) == 1
    assert result.items == engine.recommend(replace(context, limit=3)).items


def test_APRKB_G1_TC_013_mmr_uses_similarity_penalty(context):
    rows = [view(1, "alpha beta gamma"), view(2, "alpha beta delta"), view(3, "epsilon zeta")]
    engine, _ = pipeline(
        Loader({"generic_genre": rows}),
        {1: 1, 2: 0.95, 3: 0.8},
        MmrDiversifier(lambda_=0.5, max_similarity=1),
    )
    result = engine.recommend(replace(context, limit=3))
    assert [item.pattern.pattern_version_id.int for item in result.items] == [1, 3, 2]
    assert [item.score for item in result.items] == [1, 0.8, 0.95]


@pytest.mark.parametrize("lambda_", [0, 1])
def test_APRKB_G1_TC_014_mmr_lambda_boundaries_keep_first(context, lambda_):
    engine, _ = pipeline(
        Loader({"generic_genre": [view(1, "alpha"), view(2, "beta")]}),
        {1: 1, 2: 0.9},
        MmrDiversifier(lambda_=lambda_, max_similarity=1),
    )
    assert engine.recommend(context).items[0].pattern.pattern_version_id.int == 1


def test_APRKB_G1_TC_015_mmr_does_not_mutate_candidates(context):
    rows = [view(1, "alpha beta"), view(2, "alpha beta {x}"), view(3, "gamma")]
    engine, _ = pipeline(Loader({"generic_genre": rows}), {1: 1, 2: 0.9, 3: 0.8})
    candidates = list(engine.recommend(context).items)
    snapshot = tuple(candidates)
    MmrDiversifier(lambda_=0.7, max_similarity=0.8).diversify(candidates)
    assert tuple(candidates) == snapshot


def test_APRKB_G1_TC_016_empty_tokens_and_exact_empty_duplicate(context):
    assert frame_tokens("{topic}") == frozenset()
    assert jaccard(frozenset(), frozenset()) == 0
    rows = [view(1, ""), view(2, ""), view(3, "{a}"), view(4, "{b}")]
    engine, _ = pipeline(
        Loader({"generic_genre": rows}),
        {1: 1, 2: 0.9, 3: 0.8, 4: 0.7},
        MmrDiversifier(lambda_=0.7, max_similarity=0.85),
    )
    assert [item.pattern.pattern_version_id.int for item in engine.recommend(context).items] == [
        1,
        3,
        4,
    ]


@pytest.mark.parametrize("query", [None, "", "   ", "!?😀"])
def test_APRKB_G1_TC_017_linguistic_empty_query_is_unavailable(context, query):
    assert LinguisticScorer().score(view(), replace(context, query=query)) is None


@pytest.mark.parametrize(
    "query,frame,expected",
    [
        ("SUGGESTS suggests suggested", "We suggest {topic}.", 1.0),
        ("suggests missing", "We suggest {topic}.", 0.5),
        ("unmatched", "We suggest {topic}.", 0.0),
        ("KẾT QUẢ 😀", "Đây là kết quả.", 1.0),
    ],
)
def test_APRKB_G1_TC_018_linguistic_sets_partial_zero_and_unicode(context, query, frame, expected):
    assert LinguisticScorer().score(view(frame=frame), replace(context, query=query)) == expected
    assert keyword_tokens("SUGGESTS suggests suggested") == {"suggest"}


@pytest.mark.parametrize("limit", [1, 100])
def test_APRKB_G1_TC_019_request_limit_valid_boundaries(limit):
    assert RecommendationRequest(limit=limit).limit == limit


@pytest.mark.parametrize("limit", [0, -1, 101, "bad"])
def test_APRKB_G1_TC_020_request_limit_invalid_boundaries(limit):
    with pytest.raises(ValidationError):
        RecommendationRequest(limit=limit)


@pytest.mark.parametrize("size", [0, 499, 500])
def test_APRKB_G1_TC_021_query_length_valid(size):
    assert len(RecommendationRequest(query="x" * size).query) == size


def test_APRKB_G1_TC_022_query_length_rejects_501():
    with pytest.raises(ValidationError):
        RecommendationRequest(query="x" * 501)


@pytest.mark.parametrize("journal", ["not-a-uuid", "1", ""])
def test_APRKB_G1_TC_023_journal_id_malformed(journal):
    with pytest.raises(ValidationError):
        RecommendationRequest(journal_id=journal)


def test_APRKB_G1_TC_024_legacy_response_defaults_are_independent():
    item = dict(
        pattern_version_id=UUID(int=2),
        canonical_frame="We suggest {topic}.",
        score=1,
        breakdown={"intent": 1},
        fallback_tier="generic_genre",
        explanations=["Intent: 1.000"],
        source_type="authored",
        version_no=1,
        license_code=None,
        license_name=None,
        license_flag=False,
        source_reference=None,
        article_id=None,
    )
    payload = dict(
        items=[item],
        excluded={},
        policy_versions={},
        recommendation_id=UUID(int=1),
        context_hash="legacy-context",
    )
    first, second = RecommendationResponse(**payload), RecommendationResponse(**payload)
    assert first.fallback_trace == second.fallback_trace == []
    first.fallback_trace.append(FallbackTraceEntry(tier="generic_genre", accepted_count=0))
    assert second.fallback_trace == []
    assert first.items[0].explanation_details == second.items[0].explanation_details == []
    first.items[0].explanation_details.append(
        ExplanationDetail(criterion="intent", value=1, weight=1, available=True)
    )
    assert second.items[0].explanation_details == []


@pytest.mark.parametrize("field", ["lambda_", "max_similarity"])
@pytest.mark.parametrize("value", [0, 1])
def test_APRKB_G1_TC_025_diversity_policy_accepts_boundaries(field, value):
    payload = {"version": "0.1.0", "lambda_": 0.7, "max_similarity": 0.85, field: value}
    assert getattr(DiversityPolicy.model_validate(payload), field) == value


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
def test_APRKB_G1_TC_026_same_move_policy_rejects_invalid(value, policy_bundle):
    payload = policy_bundle.ranking_weights.model_dump()
    payload["intent_scores"]["same_move"] = value
    with pytest.raises(ValidationError):
        RankingWeightsPolicy.model_validate(payload)


@pytest.mark.parametrize("version", ["0.3", "v0.3.0", "", "0.3.0-beta"])
def test_APRKB_G1_TC_027_policy_requires_semantic_version(version):
    with pytest.raises(ValidationError):
        DiversityPolicy(version=version, lambda_=0.7, max_similarity=0.85)


def test_APRKB_G1_TC_028_policy_rejects_unknown_settings():
    with pytest.raises(ValidationError):
        DiversityPolicy.model_validate(
            {
                "version": "0.1.0",
                "lambda_": 0.7,
                "max_similarity": 0.85,
                "embedding_model": "unused",
            }
        )


@pytest.mark.parametrize(
    "field", ["section", "move", "intent", "genre", "claim_type", "evidence_level", "discipline"]
)
@pytest.mark.parametrize("value", [12, ["INTRO"], {"code": "INTRO"}])
def test_APRKB_G1_TC_029_optional_codes_reject_wrong_types(field, value):
    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate({field: value})
    assert getattr(RecommendationRequest.model_validate({field: None}), field) is None


@pytest.mark.parametrize("limit", [0, -1])
def test_APRKB_G1_TC_030_context_rejects_nonpositive_limit(context, limit):
    with pytest.raises(ValueError, match="positive"):
        replace(context, limit=limit)
