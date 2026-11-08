"""Read-only DTO consumed by recommendation gates and scorers."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PatternView:
    pattern_version_id: UUID
    status: str
    intent_code: str
    canonical_frame: str
    claim_type: str | None
    epistemic_strength: str | None
    allowed_sections: tuple[str, ...]
    allowed_genres: tuple[str, ...]
    source_type: str
    license_allows_display: bool
    license_flag: bool = False
    version_no: int = 1
    license_code: str | None = None
    license_name: str | None = None
    source_reference: str | None = None
    article_id: UUID | None = None
    evidence_min: str | None = None
    forbidden_contexts: tuple[str, ...] = ()
    move_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_sections", tuple(self.allowed_sections))
        object.__setattr__(self, "allowed_genres", tuple(self.allowed_genres))
        object.__setattr__(self, "forbidden_contexts", tuple(self.forbidden_contexts))
