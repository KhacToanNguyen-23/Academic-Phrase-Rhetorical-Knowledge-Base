"""Unit tests for the validation domain."""

from uuid import uuid4

from aprkb.modules.recommendation.gates import build_gates
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.pipeline import ValidationPipeline
from aprkb.modules.validation.rules import build_rules
from aprkb.policies.evidence import EvidencePolicy
from aprkb.shared.models import RefEnum


def pattern(**overrides):
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
