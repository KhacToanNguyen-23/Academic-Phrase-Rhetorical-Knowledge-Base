from pathlib import Path
from shutil import copytree
from uuid import uuid4

import pytest

from aprkb.modules.journals.guideline_policy import GuidelinePolicy
from aprkb.policies.evidence import EvidencePolicy
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import RankingWeightsPolicy
from aprkb.shared.models import RefEnum


def test_policy_bundle_loads_versioned_sample_policies() -> None:
    bundle = load_policy_bundle()

    assert bundle.ranking_weights.version == "0.1.0"
    assert bundle.evidence_matrix.version == "0.1.0"
    assert bundle.validation_rules.version == "0.1.0"
    assert "prove" in bundle.epistemic_markers.markers["absolute"]


def test_policy_loader_rejects_invalid_schema(tmp_path) -> None:
    source = Path(__file__).parents[3] / "src" / "aprkb" / "policies"
    policy_dir = tmp_path / "policies"
    copytree(source, policy_dir)
    (policy_dir / "ranking_weights.yaml").write_text(
        "version: 0.1.0\nweights: []\n", encoding="utf-8"
    )

    with pytest.raises(ValueError):
        load_policy_bundle(policy_dir)


def test_policy_rejects_empty_active_scorer_weights() -> None:
    with pytest.raises(ValueError):
        RankingWeightsPolicy.model_validate(
            {
                "version": "0.1.0",
                "weights": {
                    "intent": 0,
                    "discipline": 0,
                    "journal_genre": 0,
                    "evidence": 0,
                    "linguistic": 0,
                    "provenance": 0,
                },
            }
        )


def test_evidence_policy_uses_enum_order_and_fails_closed_on_unknown_values() -> None:
    bundle = load_policy_bundle()
    strength_order = {"low": 0, "moderate": 1, "high": 2, "absolute": 3}
    policy = EvidencePolicy(bundle.evidence_matrix, strength_order)

    assert policy.max_strength("causal", "single_study") == "moderate"
    assert policy.is_allowed("causal", "single_study", "low")
    assert policy.is_allowed("causal", "single_study", "moderate")
    assert not policy.is_allowed("causal", "single_study", "high")
    assert not policy.is_allowed("causal", "single_study", "absolute")
    assert not policy.is_allowed("unknown_claim", "single_study", "low")
    assert not policy.is_allowed("causal", "unknown_evidence", "low")
    assert not policy.is_allowed("causal", "single_study", "unknown_strength")
    with pytest.raises(ValueError):
        policy.max_strength("unknown_claim", "single_study")


def test_evidence_policy_can_build_order_from_reference_enum_rows() -> None:
    bundle = load_policy_bundle()
    enums = [
        RefEnum(group="epistemic_strength", code=code, label=code, order=order)
        for order, code in enumerate(("low", "moderate", "high", "absolute"), start=1)
    ]
    policy = EvidencePolicy.from_reference_enums(bundle.evidence_matrix, enums)

    assert policy.is_allowed("causal", "single_study", "moderate")
    assert not policy.is_allowed("causal", "single_study", "high")


def test_guideline_policy_caches_rules_by_journal() -> None:
    policy = GuidelinePolicy()
    journal_id = uuid4()
    rules = ({"rule_type": "style", "payload": {"value": "concise"}},)

    assert policy.get(journal_id) == ()
    policy.set(journal_id, rules)
    assert policy.get(journal_id) == rules
