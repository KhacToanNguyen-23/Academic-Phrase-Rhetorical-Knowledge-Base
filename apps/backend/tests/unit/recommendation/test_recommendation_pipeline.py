"""Unit tests for the recommendation domain."""

from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import pytest

from aprkb.modules.discipline.null_source import NullDisciplineSource
from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.diversifier import PassThroughDiversifier
from aprkb.modules.recommendation.fallback import FallbackTierLoader
from aprkb.modules.recommendation.gates import build_gates
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.recommendation.pipeline import RecommendationPipeline
from aprkb.modules.recommendation.scorers import build_scorers
from aprkb.modules.recommendation.scorers.aggregator import aggregate_scores


def pattern(**overrides) -> PatternView:
    values = {
        "pattern_version_id": uuid4(),
        "status": "approved",
        "intent_code": "report_finding",
        "canonical_frame": "The results {verb} that {finding}.",
        "claim_type": "causal",
        "epistemic_strength": "moderate",
        "allowed_sections": ["results"],
        "allowed_genres": [],
        "source_type": "authored",
        "license_allows_display": True,
    }
    values.update(overrides)
    return PatternView(**values)


def test_recommendation_context_is_immutable(context):
    with pytest.raises(FrozenInstanceError):
        context.limit = 1


def test_pattern_view_is_read_only():
    view = pattern()

    with pytest.raises(FrozenInstanceError):
        view.status = "draft"


def test_hard_gates_are_registered_in_prd_order(context, evidence_policy):
    gates = build_gates(evidence_policy=evidence_policy)

    assert [type(gate).__name__ for gate in gates] == [
        "ApprovalGate",
        "RetiredGate",
        "LicenseGate",
        "IntentSectionGate",
        "EvidenceGate",
        "GuidelineGate",
    ]
    assert all(gate.check(pattern(), context).passed for gate in gates)


@pytest.mark.parametrize(
    ("overrides", "expected_gate"),
    [
        ({"status": "draft"}, "ApprovalGate"),
        ({"status": "retired"}, "RetiredGate"),
        ({"source_type": "mined", "license_allows_display": False}, "LicenseGate"),
        ({"source_type": "unknown", "license_allows_display": True}, "LicenseGate"),
        ({"allowed_sections": ["discussion"]}, "IntentSectionGate"),
        ({"epistemic_strength": "high"}, "EvidenceGate"),
    ],
)
def test_each_hard_gate_has_a_fail_case(context, evidence_policy, overrides, expected_gate):
    gates = build_gates(evidence_policy=evidence_policy)
    result = next(gate for gate in gates if type(gate).__name__ == expected_gate).check(
        pattern(**overrides), context
    )

    assert not result.passed
    assert result.reason


def test_aggregator_renormalizes_missing_scorers_and_keeps_null_breakdown():
    total, breakdown = aggregate_scores(
        scores={"intent": 1.0, "discipline": None, "evidence": 0.5},
        weights={"intent": 0.25, "discipline": 0.25, "evidence": 0.50},
    )

    assert total == pytest.approx((1.0 * 0.25 + 0.5 * 0.50) / 0.75)
    assert breakdown == {"intent": 1.0, "discipline": None, "evidence": 0.5}


def test_aggregator_ignores_zero_weight_scorers():
    total, breakdown = aggregate_scores(
        scores={"intent": 0.5, "linguistic": 1.0},
        weights={"intent": 1.0, "linguistic": 0.0},
    )

    assert total == pytest.approx(0.5)
    assert breakdown == {"intent": 0.5, "linguistic": None}


def test_aggregator_rejects_all_zero_active_weights():
    with pytest.raises(ValueError, match="weight"):
        aggregate_scores(
            scores={"intent": 1.0, "evidence": 1.0},
            weights={"intent": 0.0, "evidence": 0.0},
        )


def test_scaffold_scorers_use_only_the_documented_values(context, evidence_policy):
    scorers = {
        scorer.key: scorer
        for scorer in build_scorers(
            discipline_source=NullDisciplineSource(), evidence_policy=evidence_policy
        )
    }
    authored = pattern()

    assert scorers["intent"].score(authored, context) == 1.0
    assert scorers["discipline"].score(authored, context) is None
    assert scorers["journal_genre"].score(authored, context) is None
    assert scorers["evidence"].score(authored, context) == 1.0
    assert scorers["linguistic"].score(authored, context) == 0.5
    assert scorers["provenance"].score(authored, context) == 1.0
    assert scorers["provenance"].score(pattern(source_type="mined"), context) == 0.7


def test_recommendation_fallback_reuses_gates_deduplicates_and_applies_limit(
    context, policy_bundle, evidence_policy
):
    shared = pattern()
    fallback_only = pattern()
    context = RecommendationContext(
        intent_code=context.intent_code,
        section_code=context.section_code,
        genre_code=context.genre_code,
        journal_id=context.journal_id,
        claim_type=context.claim_type,
        evidence_level=context.evidence_level,
        discipline_code=context.discipline_code,
        client_id=context.client_id,
        limit=2,
    )
    loader = FallbackTierLoader(
        tiers=policy_bundle.fallback_tiers.tiers,
        by_tier={
            "journal_genre": [shared],
            "similar_journal_genre": [shared, pattern(status="draft"), fallback_only],
        },
    )
    pipeline = RecommendationPipeline(
        gates=build_gates(evidence_policy=evidence_policy),
        scorers=build_scorers(
            discipline_source=NullDisciplineSource(), evidence_policy=evidence_policy
        ),
        weights=policy_bundle.ranking_weights.weights,
        tier_loader=loader,
    )

    result = pipeline.recommend(context)

    assert [item.pattern.pattern_version_id for item in result.items] == [
        shared.pattern_version_id,
        fallback_only.pattern_version_id,
    ]
    assert [item.fallback_tier for item in result.items] == [
        "journal_genre",
        "similar_journal_genre",
    ]
    assert result.excluded["GATE_APPROVAL"] == 1


def test_recommendation_does_not_load_fallback_when_primary_fills_limit(
    context, policy_bundle, evidence_policy
):
    class TrackingLoader(FallbackTierLoader):
        def __init__(self):
            super().__init__(
                tiers=policy_bundle.fallback_tiers.tiers,
                by_tier={
                    "journal_genre": [pattern()],
                    "similar_journal_genre": [pattern()],
                },
            )
            self.loaded = []

        def load(self, tier, context):
            self.loaded.append(tier)
            return super().load(tier, context)

    loader = TrackingLoader()
    pipeline = RecommendationPipeline(
        gates=build_gates(evidence_policy=evidence_policy),
        scorers=build_scorers(
            discipline_source=NullDisciplineSource(), evidence_policy=evidence_policy
        ),
        weights=policy_bundle.ranking_weights.weights,
        tier_loader=loader,
    )

    result = pipeline.recommend(replace(context, limit=1))

    assert len(result.items) == 1
    assert loader.loaded == ["journal_genre"]


def test_recommendation_ranks_the_whole_primary_tier_before_applying_limit(
    context, policy_bundle, evidence_policy
):
    primary = [
        pattern(source_type="mined"),
        pattern(source_type="authored"),
    ]
    loader = FallbackTierLoader(
        tiers=policy_bundle.fallback_tiers.tiers,
        by_tier={"journal_genre": primary, "similar_journal_genre": [pattern()]},
    )
    pipeline = RecommendationPipeline(
        gates=build_gates(evidence_policy=evidence_policy),
        scorers=build_scorers(
            discipline_source=NullDisciplineSource(), evidence_policy=evidence_policy
        ),
        weights=policy_bundle.ranking_weights.weights,
        tier_loader=loader,
    )

    result = pipeline.recommend(replace(context, limit=1))

    assert result.items[0].pattern.pattern_version_id == primary[1].pattern_version_id


def test_scaffold_diversifier_preserves_ranked_order():
    ranked = [pattern(), pattern()]

    assert PassThroughDiversifier().diversify(ranked) == ranked


def test_recommendation_applies_limit_after_diversification(
    context, policy_bundle, evidence_policy
):
    class DuplicatingDiversifier:
        def diversify(self, items):
            return list(items) + list(items)

    loader = FallbackTierLoader(
        tiers=policy_bundle.fallback_tiers.tiers,
        by_tier={"journal_genre": [pattern()]},
    )
    pipeline = RecommendationPipeline(
        gates=build_gates(evidence_policy=evidence_policy),
        scorers=build_scorers(
            discipline_source=NullDisciplineSource(), evidence_policy=evidence_policy
        ),
        weights=policy_bundle.ranking_weights.weights,
        tier_loader=loader,
        diversifier=DuplicatingDiversifier(),
    )

    assert len(pipeline.recommend(replace(context, limit=1)).items) == 1
