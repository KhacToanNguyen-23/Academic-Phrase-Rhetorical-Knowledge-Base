"""Shared evidence-to-strength policy for recommendation gates and V02.

The versioned runtime matrix is configured in ``evidence_matrix.yaml``. Strength
ordering comes from the seeded reference enums, as required by SCAFFOLD_PRD.md
§4.6. Keep this as the single comparison implementation used by both paths.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from aprkb.policies.schemas import EvidenceMatrixPolicy

if TYPE_CHECKING:
    from aprkb.shared.models import RefEnum


@dataclass(frozen=True)
class EvidencePolicy:
    evidence_matrix: EvidenceMatrixPolicy
    strength_order: dict[str, int]

    @classmethod
    def from_reference_enums(
        cls, evidence_matrix: EvidenceMatrixPolicy, enums: Iterable[RefEnum]
    ) -> EvidencePolicy:
        strength_order = {
            enum.code: enum.order for enum in enums if enum.group == "epistemic_strength"
        }
        return cls(evidence_matrix, strength_order)

    def __post_init__(self) -> None:
        if not self.strength_order or len(set(self.strength_order.values())) != len(
            self.strength_order
        ):
            raise ValueError("strength_order must be non-empty and have unique order values")
        configured = {self.evidence_matrix.default_max_strength}
        configured.update(
            strength
            for cells in self.evidence_matrix.matrix.values()
            for strength in cells.values()
        )
        if not configured <= self.strength_order.keys():
            raise ValueError("strength_order is missing configured reference enum values")

    def max_strength(self, claim_type: str, evidence_level: str) -> str:
        cells = self.evidence_matrix.matrix.get(claim_type)
        known_evidence = {
            evidence for row in self.evidence_matrix.matrix.values() for evidence in row
        }
        if cells is None or evidence_level not in known_evidence:
            raise ValueError(f"Unknown evidence policy cell: {claim_type}/{evidence_level}")
        return cells.get(evidence_level, self.evidence_matrix.default_max_strength)

    def is_allowed(self, claim_type: str, evidence_level: str, strength: str) -> bool:
        try:
            maximum = self.max_strength(claim_type, evidence_level)
            return self.strength_order[strength] <= self.strength_order[maximum]
        except (KeyError, ValueError):
            return False

    def alignment_score(self, claim_type: str, evidence_level: str, strength: str) -> float | None:
        """Score proximity to the strongest policy-supported level after hard gating."""
        try:
            maximum = self.strength_order[self.max_strength(claim_type, evidence_level)]
            candidate = self.strength_order[strength]
        except (KeyError, ValueError):
            return None
        span = max(self.strength_order.values()) - min(self.strength_order.values())
        return 1.0 if span == 0 else 1.0 - abs(maximum - candidate) / span
