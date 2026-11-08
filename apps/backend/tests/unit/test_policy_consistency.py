"""Characterize unlabelled patterns without changing BR-03 policy defaults."""

from dataclasses import replace
from uuid import uuid4

import pytest

from aprkb.modules.recommendation.gates.evidence import EvidenceGate
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.recommendation.scorers.implementations import EvidenceScorer
from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.rules.base import Severity
from aprkb.modules.validation.rules.v02_claim_evidence import V02ClaimEvidenceRule


@pytest.mark.parametrize("claim_type", [None, "causal"])
@pytest.mark.parametrize("evidence_level", [None, "single_study"])
@pytest.mark.parametrize(
    "text,has_marker",
    [("The results suggest a relationship.", True), ("A relationship was observed.", False)],
)
def test_unlabelled_evidence_paths(
    context, evidence_policy, policy_bundle, claim_type, evidence_level, text, has_marker
):
    pattern = PatternView(
        pattern_version_id=uuid4(),
        status="approved",
        intent_code="report_finding",
        canonical_frame=text,
        claim_type=None,
        epistemic_strength=None,
        allowed_sections=(),
        allowed_genres=(),
        source_type="authored",
        license_allows_display=True,
    )
    ctx = replace(context, claim_type=claim_type, evidence_level=evidence_level)

    assert EvidenceGate(evidence_policy).check(pattern, ctx).passed is (evidence_level is None)
    # None is the documented unavailable signal, never a fabricated zero or exception.
    assert EvidenceScorer(evidence_policy).score(pattern, ctx) is None
    assert evidence_policy.alignment_score(claim_type or "", evidence_level or "", "") is None

    rule = V02ClaimEvidenceRule(
        evidence_policy=evidence_policy,
        lexicon=policy_bundle.epistemic_markers,
        severity=Severity.BLOCK,
    )
    result = rule.evaluate(
        text,
        ValidationContext(claim_type=claim_type or "", evidence_level=evidence_level or ""),
    )
    # V02 reads markers from text, not the missing pattern metadata.
    blocked = has_marker and (claim_type is None or evidence_level is None)
    assert result.severity == (Severity.BLOCK if blocked else Severity.PASS)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="BR-03 owner decision: unlabelled pattern fails EvidenceGate but marker-free V02 passes",
)
def test_unlabelled_marker_free_gate_and_v02_agree(context, evidence_policy, policy_bundle):
    pattern = PatternView(
        pattern_version_id=uuid4(),
        status="approved",
        intent_code="report_finding",
        canonical_frame="A relationship was observed.",
        claim_type=None,
        epistemic_strength=None,
        allowed_sections=(),
        allowed_genres=(),
        source_type="authored",
        license_allows_display=True,
    )
    ctx = replace(context, claim_type=None, evidence_level="single_study")
    gate = EvidenceGate(evidence_policy).check(pattern, ctx)
    rule = V02ClaimEvidenceRule(
        evidence_policy=evidence_policy,
        lexicon=policy_bundle.epistemic_markers,
        severity=Severity.BLOCK,
    )
    result = rule.evaluate(
        pattern.canonical_frame,
        ValidationContext(claim_type="", evidence_level="single_study"),
    )
    assert gate.passed == (result.severity == Severity.PASS)
