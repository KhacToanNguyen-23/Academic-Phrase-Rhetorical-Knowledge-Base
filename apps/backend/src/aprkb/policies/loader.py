"""Load and validate all packaged runtime policies."""

from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError

from aprkb.policies.schemas import (
    EpistemicMarkersPolicy,
    EvidenceMatrixPolicy,
    FallbackTiersPolicy,
    LicensePolicy,
    MiningFilterPolicy,
    RankingWeightsPolicy,
    ValidationRulesPolicy,
)


@dataclass(frozen=True)
class PolicyBundle:
    ranking_weights: RankingWeightsPolicy
    license: LicensePolicy
    fallback_tiers: FallbackTiersPolicy
    evidence_matrix: EvidenceMatrixPolicy
    validation_rules: ValidationRulesPolicy
    epistemic_markers: EpistemicMarkersPolicy
    mining_filter: MiningFilterPolicy


def _load[PolicyModel: BaseModel](path: Path, model: type[PolicyModel]) -> PolicyModel:
    try:
        with path.open(encoding="utf-8") as policy_file:
            payload = yaml.safe_load(policy_file)
        return model.model_validate(payload)
    except (OSError, yaml.YAMLError, ValidationError, TypeError) as error:
        raise ValueError(f"Invalid policy file {path.name}: {error}") from error


def load_policy_bundle(policy_dir: Path | str | None = None) -> PolicyBundle:
    """Load all policy files, failing startup on missing or invalid policy data."""
    root = Path(policy_dir) if policy_dir is not None else Path(__file__).parent
    return PolicyBundle(
        ranking_weights=_load(root / "ranking_weights.yaml", RankingWeightsPolicy),
        license=_load(root / "license_policy.yaml", LicensePolicy),
        fallback_tiers=_load(root / "fallback_tiers.yaml", FallbackTiersPolicy),
        evidence_matrix=_load(root / "evidence_matrix.yaml", EvidenceMatrixPolicy),
        validation_rules=_load(root / "validation_rules.yaml", ValidationRulesPolicy),
        epistemic_markers=_load(
            root / "lexicon" / "epistemic_markers.yaml", EpistemicMarkersPolicy
        ),
        mining_filter=_load(root / "mining_filter.yaml", MiningFilterPolicy),
    )
