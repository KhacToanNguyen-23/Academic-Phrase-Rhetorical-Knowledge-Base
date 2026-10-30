"""HTTP schemas for pattern discovery and append-only version writes."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatternVersionCreate(BaseModel):
    canonical_frame: str = Field(min_length=1)
    slots: dict[str, object] = Field(default_factory=dict)
    epistemic_strength: Literal["low", "moderate", "high", "absolute"]
    claim_type: Literal["descriptive", "causal", "comparative", "generalization"]
    change_note: str | None = None


class PatternCreate(PatternVersionCreate):
    intent_code: str
    allowed_sections: list[str] = Field(min_length=1)
    allowed_genres: list[str] = Field(default_factory=list)
    source_type: Literal["authored"] = "authored"


class PatternVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pattern_id: UUID
    version_no: int
    canonical_frame: str
    slots: dict[str, object]
    epistemic_strength: str
    claim_type: str
    change_note: str | None


class PatternSummary(BaseModel):
    id: UUID
    status: str
    intent_code: str
    canonical_frame: str | None
    version_no: int | None


class PatternDetail(PatternSummary):
    current_version_id: UUID | None
    slots: dict[str, object] | None
    epistemic_strength: str | None
    claim_type: str | None
    allowed_sections: list[str]
    allowed_genres: list[str]
