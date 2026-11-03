"""Pin the evidence matrix cells and the fail-closed policy behaviour."""

import pytest

STRENGTH_ORDER = {"low": 1, "moderate": 2, "high": 3, "absolute": 4}
EVIDENCE_LEVELS = (
    "none",
    "anecdotal",
    "single_study",
    "multiple_consistent",
    "systematic_synthesis",
)
STRENGTHS = ("low", "moderate", "high", "absolute")
APPROVED_CLAIM_TYPES = ("descriptive", "causal")

EXPECTED_MAX_STRENGTH = {
    "descriptive": {
        "none": "low",
        "anecdotal": "moderate",
        "single_study": "high",
        "multiple_consistent": "high",
        "systematic_synthesis": "high",
    },
    "causal": {
        "none": "low",
        "anecdotal": "low",
        "single_study": "moderate",
        "multiple_consistent": "high",
        "systematic_synthesis": "high",
    },
}


@pytest.mark.parametrize("claim_type", APPROVED_CLAIM_TYPES)
@pytest.mark.parametrize("evidence_level", EVIDENCE_LEVELS)
@pytest.mark.parametrize("strength", STRENGTHS)
def test_evidence_matrix_cell(evidence_policy, claim_type, evidence_level, strength) -> None:
    maximum = EXPECTED_MAX_STRENGTH[claim_type][evidence_level]

    assert evidence_policy.max_strength(claim_type, evidence_level) == maximum
    expected_allowed = (
        strength != "absolute" and STRENGTH_ORDER[strength] <= STRENGTH_ORDER[maximum]
    )
    assert evidence_policy.is_allowed(claim_type, evidence_level, strength) is expected_allowed


@pytest.mark.parametrize("claim_type", ("comparative", "generalization"))
@pytest.mark.parametrize("evidence_level", EVIDENCE_LEVELS)
@pytest.mark.parametrize("strength", STRENGTHS)
def test_unapproved_claim_types_fail_closed(
    evidence_policy, claim_type, evidence_level, strength
) -> None:
    with pytest.raises(ValueError):
        evidence_policy.max_strength(claim_type, evidence_level)

    assert evidence_policy.is_allowed(claim_type, evidence_level, strength) is False


@pytest.mark.parametrize("strength", STRENGTHS)
def test_unknown_evidence_level_fails_closed(evidence_policy, strength) -> None:
    with pytest.raises(ValueError):
        evidence_policy.max_strength("descriptive", "unknown_evidence")

    assert evidence_policy.is_allowed("descriptive", "unknown_evidence", strength) is False


@pytest.mark.parametrize("strength", STRENGTHS)
def test_unknown_claim_type_fails_closed(evidence_policy, strength) -> None:
    with pytest.raises(ValueError):
        evidence_policy.max_strength("unknown_claim", "single_study")

    assert evidence_policy.is_allowed("unknown_claim", "single_study", strength) is False
