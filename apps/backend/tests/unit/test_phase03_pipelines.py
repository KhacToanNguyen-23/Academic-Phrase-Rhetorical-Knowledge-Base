"""TDD contracts for the PRD's pure recommendation, validation and mining pipelines."""

from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import pytest

from aprkb.modules.corpus.parsers.base import DocumentParser
from aprkb.modules.corpus.parsers.pdf_parser import PdfParserStub
from aprkb.modules.discipline.null_source import NullDisciplineSource
from aprkb.modules.journals.fingerprint import JournalFingerprintService
from aprkb.modules.mining.candidate_writer import CandidateDraft, CandidateWriter
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.diversifier import PassThroughDiversifier
from aprkb.modules.recommendation.fallback import FallbackTierLoader
from aprkb.modules.recommendation.gates import build_gates
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.recommendation.pipeline import RecommendationPipeline
from aprkb.modules.recommendation.scorers import build_scorers
from aprkb.modules.recommendation.scorers.aggregator import aggregate_scores
from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.pipeline import ValidationPipeline
from aprkb.modules.validation.rules import build_rules
from aprkb.policies.evidence import EvidencePolicy
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import EpistemicMarkersPolicy, MiningFilterPolicy
from aprkb.shared.models import RefEnum


@pytest.fixture
def policy_bundle():
    return load_policy_bundle()


@pytest.fixture
def evidence_policy(policy_bundle):
    return EvidencePolicy.from_reference_enums(
        policy_bundle.evidence_matrix,
        [
            RefEnum(group="epistemic_strength", code="low", label="Low", order=1),
            RefEnum(group="epistemic_strength", code="moderate", label="Moderate", order=2),
            RefEnum(group="epistemic_strength", code="high", label="High", order=3),
            RefEnum(group="epistemic_strength", code="absolute", label="Absolute", order=4),
        ],
    )


@pytest.fixture
def context():
    return RecommendationContext(
        intent_code="report_finding",
        section_code="results",
        genre_code=None,
        journal_id=None,
        claim_type="causal",
        evidence_level="single_study",
        discipline_code=None,
        client_id=uuid4(),
        limit=10,
    )


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


def test_null_discipline_source_and_fingerprint_remain_stubs():
    journal = object()

    assert NullDisciplineSource().classify_journal(journal) is None
    assert JournalFingerprintService().compute(journal) is None


def test_pdf_parser_implements_document_parser_interface_as_a_stub():
    parser = PdfParserStub()

    assert isinstance(parser, DocumentParser)
    assert parser.supports("application/pdf")
    with pytest.raises(NotImplementedError):
        parser.parse(b"%PDF-1.7")


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


def test_v02_blocks_prove_with_single_study_and_matches_evidence_gate(
    context, evidence_policy, policy_bundle
):
    validation_context = ValidationContext(
        claim_type="causal",
        evidence_level="single_study",
        epistemic_strength="absolute",
    )
    rules = build_rules(
        evidence_policy=evidence_policy,
        lexicon=policy_bundle.epistemic_markers,
        policy=policy_bundle.validation_rules,
    )
    v02 = next(rule for rule in rules if rule.code == "V02")
    result = v02.evaluate("This proves the intervention caused the outcome.", validation_context)
    gate = next(
        gate
        for gate in build_gates(evidence_policy=evidence_policy)
        if gate.code == "GATE_EVIDENCE"
    ).check(pattern(epistemic_strength="absolute"), context)

    assert result.severity.value == "block"
    assert not gate.passed
    assert (result.severity.value == "block") == (not gate.passed)


def test_v02_fails_closed_when_marker_strength_is_missing_from_reference_enums(policy_bundle):
    evidence_policy = EvidencePolicy.from_reference_enums(
        policy_bundle.evidence_matrix,
        [
            RefEnum(group="epistemic_strength", code="low", label="Low", order=1),
            RefEnum(group="epistemic_strength", code="moderate", label="Moderate", order=2),
            RefEnum(group="epistemic_strength", code="high", label="High", order=3),
        ],
    )
    rule = next(
        item
        for item in build_rules(
            evidence_policy=evidence_policy,
            lexicon=policy_bundle.epistemic_markers,
            policy=policy_bundle.validation_rules,
        )
        if item.code == "V02"
    )

    result = rule.evaluate(
        "This proves the intervention caused the outcome.",
        ValidationContext(claim_type="causal", evidence_level="single_study"),
    )

    assert result.severity.value == "block"


def test_validation_pipeline_runs_v01_through_v08_and_todo_rules_pass(
    evidence_policy, policy_bundle
):
    rules = build_rules(
        evidence_policy=evidence_policy,
        lexicon=policy_bundle.epistemic_markers,
        policy=policy_bundle.validation_rules,
    )
    pipeline = ValidationPipeline(rules=rules)
    context = ValidationContext(
        claim_type="descriptive",
        evidence_level="single_study",
        epistemic_strength="moderate",
    )

    results = pipeline.validate("The study suggests a possible relationship.", context)

    assert [result.code for result in results] == [f"V{i:02}" for i in range(1, 9)]
    assert all(result.severity.value == "pass" for result in results if result.code != "V02")


def test_mining_registry_has_deterministic_order_and_requirement_tags(policy_bundle):
    stages = build_stages(policy=policy_bundle.mining_filter)

    assert [stage.name for stage in stages] == [
        "sentence_filter",
        "move_classifier",
        "epistemic_tagger",
        "slot_abstractor",
        "frame_normalizer",
        "clusterer",
        "dedup_matcher",
    ]
    for stage in stages[1:]:
        assert stage.requirement_id


def test_sentence_filter_removes_inline_citations_but_keeps_remaining_sentence():
    stage = SentenceFilter(min_words=1, max_words=100)
    item = MiningItem(
        text="The result was stable [12] (Nguyen, 2020).",
        source_sentence_ids=[uuid4()],
    )

    results = stage.process([item])

    assert len(results) == 1
    assert "[12]" not in results[0].text
    assert "(Nguyen, 2020)" not in results[0].text
    assert "The result was stable" in results[0].text


def test_sentence_filter_applies_configured_word_bounds():
    stage = SentenceFilter(min_words=2, max_words=4)
    items = [
        MiningItem(text="Short.", source_sentence_ids=[uuid4()]),
        MiningItem(text="One two three four five.", source_sentence_ids=[uuid4()]),
        MiningItem(text="One two three.", source_sentence_ids=[uuid4()]),
    ]

    results = stage.process(items)

    assert [item.text for item in results] == ["One two three."]


def test_mining_filter_thresholds_come_from_validated_policy():
    policy = MiningFilterPolicy.model_validate(
        {"version": "0.1.0", "sentence_filter": {"min_words": 1, "max_words": 10}}
    )
    stage = build_stages(policy=policy)[0]

    assert stage.process([MiningItem(text="Short sentence.", source_sentence_ids=[uuid4()])])


def test_invalid_filter_bounds_and_blank_lexicon_entries_are_rejected():
    with pytest.raises(ValueError, match="min_words"):
        MiningFilterPolicy.model_validate(
            {"version": "0.1.0", "sentence_filter": {"min_words": 11, "max_words": 10}}
        )
    with pytest.raises(ValueError, match="markers"):
        EpistemicMarkersPolicy.model_validate(
            {
                "version": "0.1.0",
                "markers": {
                    "low": [" "],
                    "moderate": ["suggest"],
                    "high": ["show"],
                    "absolute": ["prove"],
                },
            }
        )


def test_candidate_writer_rejects_missing_source_sentence_ids():
    writer = CandidateWriter(repository=None)
    draft = CandidateDraft(canonical_frame="The results {verb}.", source_sentence_ids=[])

    with pytest.raises(ValueError, match="source_sentence_ids"):
        writer.write(draft)
