"""Unit tests for V02 recognition of inflected epistemic markers."""

import pytest

from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.rules import build_rules
from aprkb.modules.validation.rules.base import Severity
from aprkb.modules.validation.rules.v02_claim_evidence import V02ClaimEvidenceRule

SINGLE_WORD_INFLECTIONS = [
    ("show", "show"),
    ("show", "shows"),
    ("show", "showed"),
    ("show", "shown"),
    ("show", "showing"),
    ("demonstrate", "demonstrates"),
    ("demonstrate", "demonstrated"),
    ("demonstrate", "demonstrating"),
    ("confirm", "confirms"),
    ("confirm", "confirmed"),
    ("confirm", "confirming"),
    ("suggest", "suggests"),
    ("suggest", "suggested"),
    ("suggest", "suggesting"),
    ("indicate", "indicates"),
    ("indicate", "indicated"),
    ("indicate", "indicating"),
    ("prove", "prove"),
    ("prove", "proves"),
    ("prove", "proved"),
    ("prove", "proven"),
    ("prove", "proving"),
]

MULTI_WORD_INFLECTIONS = [
    ("appears to", "appear to"),
    ("appears to", "appears to"),
    ("appears to", "appeared to"),
    ("appears to", "appearing to"),
    ("establish beyond doubt", "establish beyond doubt"),
    ("establish beyond doubt", "establishes beyond doubt"),
    ("establish beyond doubt", "established beyond doubt"),
    ("establish beyond doubt", "establishing beyond doubt"),
]


def build_v02(evidence_policy, policy_bundle):
    return next(
        rule
        for rule in build_rules(
            evidence_policy=evidence_policy,
            lexicon=policy_bundle.epistemic_markers,
            policy=policy_bundle.validation_rules,
        )
        if rule.code == "V02"
    )


@pytest.mark.parametrize(("marker", "form"), SINGLE_WORD_INFLECTIONS)
def test_single_word_verb_markers_match_inflections(marker, form):
    assert V02ClaimEvidenceRule._contains_marker(f"The results {form} that X.", marker)


@pytest.mark.parametrize(("marker", "form"), MULTI_WORD_INFLECTIONS)
def test_multi_word_markers_inflect_their_leading_verb(marker, form):
    assert V02ClaimEvidenceRule._contains_marker(f"The findings {form} the claim.", marker)


@pytest.mark.parametrize(
    ("text", "marker"),
    [
        ("The showcase was updated.", "show"),
        ("The mayor attended the meeting.", "may"),
        ("The result couldn't be reproduced.", "could"),
        ("The results were unclear.", "show"),
    ],
)
def test_marker_substrings_inside_other_words_do_not_match(text, marker):
    assert not V02ClaimEvidenceRule._contains_marker(text, marker)


@pytest.mark.parametrize("marker", ["may", "might", "could", "possibly", "always", "is likely"])
def test_non_verb_markers_keep_exact_matching(marker):
    assert V02ClaimEvidenceRule._contains_marker(f"The findings {marker} hold.", marker)
    assert not V02ClaimEvidenceRule._contains_marker(f"The findings {marker}s hold.", marker)


@pytest.mark.parametrize(
    "form",
    ["showed", "shown", "proved", "proven", "demonstrated", "confirmed", "suggested", "indicated"],
)
def test_v02_blocks_inflected_markers_above_the_evidence_ceiling(
    form, evidence_policy, policy_bundle
):
    v02 = build_v02(evidence_policy, policy_bundle)
    context = ValidationContext(claim_type="causal", evidence_level="none")

    result = v02.evaluate(f"The results {form} that X.", context)

    assert result.severity is Severity.BLOCK
    assert result.message == (f"The marker '{form}' exceeds the evidence-supported claim strength")


def test_v02_blocks_demonstrated_but_allows_suggested_with_single_study(
    evidence_policy, policy_bundle
):
    v02 = build_v02(evidence_policy, policy_bundle)
    context = ValidationContext(claim_type="causal", evidence_level="single_study")
    text = "These results demonstrated that X."

    blocked = v02.evaluate(text, context)
    allowed = v02.evaluate("These results suggested that X.", context)

    assert blocked.severity is Severity.BLOCK
    assert blocked.message == (
        "The marker 'demonstrated' exceeds the evidence-supported claim strength"
    )
    assert blocked.span == (14, 26)
    assert allowed.severity is Severity.PASS
