"""Context passed to pure validation rules."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationContext:
    claim_type: str
    evidence_level: str
    epistemic_strength: str | None = None
    source_values: tuple[str, ...] = ()
