"""HTTP schemas for pattern discovery and append-only version writes."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatternSlotDefinition(BaseModel):
    """Typed writer slot metadata; string values remain valid for older versions."""

    type: str
    label: str | None = None
    instruction: str | None = None
    example: str | None = None
    required: bool = True
    min_length: int = Field(default=1, ge=1)


class PatternVersionCreate(BaseModel):
    canonical_frame: str = Field(min_length=1)
    slots: dict[str, PatternSlotDefinition | str] = Field(default_factory=dict)
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
    slots: dict[str, PatternSlotDefinition | str]
    epistemic_strength: str | None
    claim_type: str | None
    change_note: str | None


class RenderableVersionRead(PatternVersionRead):
    source_type: str
    intent_code: str
    intent_name: str
    status: str
    epistemic_strength_labelled: bool
    claim_type_labelled: bool
    variants: list["PatternVariantRead"]
    evidence_min: str | None
    forbidden_contexts: list[str]
    allowed_sections: list[str]
    allowed_genres: list[str]
    license_code: str | None
    license_name: str | None
    license_allows_display: bool
    license_flag: bool
    article_id: UUID | None
    source_reference: str | None
    source_sentence_count: int
    discipline_affinities: list["PatternDisciplineAffinityRead"]


class PatternVariantRead(BaseModel):
    text: str
    register_name: str | None = Field(alias="register")


class PatternDisciplineAffinityRead(BaseModel):
    discipline_code: str
    score: float


class PatternSummary(BaseModel):
    id: UUID
    status: str
    intent_code: str
    move_code: str | None = None
    intent_name: str
    canonical_frame: str | None
    version_no: int | None
    current_version_id: UUID | None
    slots: dict[str, PatternSlotDefinition | str] | None
    epistemic_strength: str | None
    epistemic_strength_labelled: bool
    claim_type: str | None
    claim_type_labelled: bool
    variants: list[PatternVariantRead]
    evidence_min: str | None
    forbidden_contexts: list[str]
    allowed_sections: list[str]
    allowed_genres: list[str]
    source_type: str
    license_code: str | None
    license_name: str | None
    license_allows_display: bool
    license_flag: bool
    article_id: UUID | None
    source_reference: str | None
    source_sentence_count: int
    discipline_affinities: list[PatternDisciplineAffinityRead]


class PatternDetail(PatternSummary):
    pass
