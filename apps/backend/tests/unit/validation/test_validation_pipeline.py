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


def test_validation_pipeline_reports_unavailable_checks(evidence_policy, policy_bundle):
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
    assert all(not result.applied for result in results if result.code not in {"V02", "V03", "V06"})
    assert next(result for result in results if result.code == "V03").applied
    assert next(result for result in results if result.code == "V06").applied
    assert all(
        result.severity.value == "unavailable"
        for result in results
        if result.code not in {"V02", "V03", "V06"}
    )
    assert not pipeline.run("The study suggests a possible relationship.", context).complete


def test_v03_blocks_unsupported_numbers_doi_and_citations(evidence_policy, policy_bundle):
    rules = build_rules(
        evidence_policy=evidence_policy,
        lexicon=policy_bundle.epistemic_markers,
        policy=policy_bundle.validation_rules,
    )
    v03 = next(rule for rule in rules if rule.code == "V03")
    context = ValidationContext(claim_type="descriptive", evidence_level="single_study")

    for text in (
        "The result was significant (p < 0.05).",
        "The rate increased by 45%.",
        "See https://doi.org/10.1234/example.",
        "Prior work reported this (Smith, 2020).",
    ):
        result = v03.evaluate(text, context)
        assert result.severity.value == "block"
        assert result.applied
        assert result.span is not None


def test_v03_accepts_numeric_and_bibliographic_values_in_supplied_context(
    evidence_policy, policy_bundle
):
    rules = build_rules(
        evidence_policy=evidence_policy,
        lexicon=policy_bundle.epistemic_markers,
        policy=policy_bundle.validation_rules,
    )
    v03 = next(rule for rule in rules if rule.code == "V03")
    text = "p < 0.05; 45%; 10.1234/example; (Smith, 2020)."
    context = ValidationContext(
        claim_type="descriptive",
        evidence_level="single_study",
        source_values=(text,),
    )

    assert v03.evaluate(text, context).severity.value == "pass"


def test_v03_does_not_treat_a_larger_number_as_support_for_a_smaller_number(
    evidence_policy, policy_bundle
):
    rules = build_rules(
        evidence_policy=evidence_policy,
        lexicon=policy_bundle.epistemic_markers,
        policy=policy_bundle.validation_rules,
    )
    v03 = next(rule for rule in rules if rule.code == "V03")
    context = ValidationContext(
        claim_type="descriptive",
        evidence_level="single_study",
        source_values=("The sample included 50 participants.",),
    )

    result = v03.evaluate("The sample included 5 participants.", context)

    assert result.severity.value == "block"


def test_v06_warns_on_configured_informal_style_phrase(evidence_policy, policy_bundle):
    rules = build_rules(
        evidence_policy=evidence_policy,
        lexicon=policy_bundle.epistemic_markers,
        policy=policy_bundle.validation_rules,
    )
    v06 = next(rule for rule in rules if rule.code == "V06")

    result = v06.evaluate(
        "The outcome was really interesting.",
        ValidationContext(claim_type="descriptive", evidence_level="single_study"),
    )

    assert result.severity.value == "warn"
    assert result.span == (16, 22)
