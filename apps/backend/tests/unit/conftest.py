"""Shared fixtures for unit tests."""

from uuid import uuid4

import pytest

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.policies.evidence import EvidencePolicy
from aprkb.policies.loader import load_policy_bundle
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
