"""Unit tests for V02 inflection metadata in the epistemic markers policy."""

import pytest

from aprkb.modules.validation.rules.base import Severity
from aprkb.modules.validation.rules.v02_claim_evidence import V02ClaimEvidenceRule
from aprkb.policies.schemas import EpistemicMarkersPolicy

MARKERS = {
    "low": ["may"],
    "moderate": ["suggest"],
    "high": ["find"],
    "absolute": ["prove"],
}


def make_policy(**overrides) -> EpistemicMarkersPolicy:
    values = {"version": "0.1.0", "markers": MARKERS}
    values.update(overrides)
    return EpistemicMarkersPolicy.model_validate(values)


def test_default_lexicon_declares_inflection_metadata(policy_bundle):
    markers = policy_bundle.epistemic_markers

    assert markers.irregular_forms["show"] == ["shown"]
    assert markers.irregular_forms["prove"] == ["proven"]
    assert "may" in markers.non_inflecting
    assert "always" in markers.non_inflecting


def test_irregular_forms_are_used_by_v02(evidence_policy):
    with_irregular = make_policy(irregular_forms={"find": ["found"]})
    without_irregular = make_policy()
    rule_with = V02ClaimEvidenceRule(
        evidence_policy=evidence_policy,
        lexicon=with_irregular,
        severity=Severity.BLOCK,
    )
    rule_without = V02ClaimEvidenceRule(
        evidence_policy=evidence_policy,
        lexicon=without_irregular,
        severity=Severity.BLOCK,
    )

    assert rule_with._contains_marker("The study found that X.", "find")
    assert not rule_without._contains_marker("The study found that X.", "find")


@pytest.mark.parametrize(
    "overrides",
    [
        {"non_inflecting": ["not_declared"]},
        {"non_inflecting": ["may", "may"]},
        {"non_inflecting": [""]},
        {"irregular_forms": {"find": []}},
    ],
)
def test_policy_rejects_invalid_inflection_metadata(overrides):
    with pytest.raises(ValueError):
        make_policy(**overrides)


def test_policy_defaults_optional_inflection_metadata():
    policy = EpistemicMarkersPolicy.model_validate({"version": "0.1.0", "markers": MARKERS})

    assert policy.irregular_forms == {}
    assert policy.non_inflecting == []
