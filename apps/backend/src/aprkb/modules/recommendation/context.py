"""Immutable context passed to pure recommendation components."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RecommendationContext:
    intent_code: str
    section_code: str
    genre_code: str | None
    journal_id: UUID | None
    claim_type: str | None
    evidence_level: str | None
    discipline_code: str | None
    client_id: UUID
    limit: int = 10

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("limit must be positive")
