"""Read and curator-write schemas for Academic Phrase Bank metadata."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from aprkb.modules.patterns.schemas import PatternSummary


class FunctionOption(BaseModel):
    code: str
    label: str
    purpose: str
    version: str
    status: str
    family_code: str
    family_label: str


class PragmaticFeatureOption(BaseModel):
    code: str
    facet: str
    label: str
    description: str | None
    version: str
    status: str


class FunctionCatalog(BaseModel):
    items: list[FunctionOption]


class PragmaticCatalog(BaseModel):
    items: list[PragmaticFeatureOption]


class DomainOption(BaseModel):
    code: str
    label: str
    version: str


class DomainCatalog(BaseModel):
    items: list[DomainOption]


class UsageProfileRead(BaseModel):
    section_code: str | None
    section_label: str | None
    genre_code: str | None
    language_code: str
    register_code: str | None
    register_version: str | None
    discipline_code: str | None
    audience: str | None
    preferred_usage: str | None


class PragmaticTagRead(BaseModel):
    code: str
    version: str
    facet: str
    label: str
    strength_note: str | None
    context_note: str | None


class PhraseExampleRead(BaseModel):
    kind: Literal["positive", "negative", "revised"]
    text: str
    explanation: str | None
    origin_kind: str
    source_ref: str | None
    license_id: UUID | None
    license_code: str | None
    license_allows_display: bool | None


class PhraseCaveatRead(BaseModel):
    code: str
    severity: str
    message: str


class AcademicPhraseRead(PatternSummary):
    communicative_functions: list[dict[str, object]] = Field(default_factory=list)
    move_links: list[dict[str, object]] = Field(default_factory=list)
    step_links: list[dict[str, object]] = Field(default_factory=list)
    usage_profiles: list[UsageProfileRead] = Field(default_factory=list)
    pragmatic_tags: list[PragmaticTagRead] = Field(default_factory=list)
    examples: list[PhraseExampleRead] = Field(default_factory=list)
    caveats: list[PhraseCaveatRead] = Field(default_factory=list)


class AcademicPhrasePage(BaseModel):
    items: list[AcademicPhraseRead]
    total: int
    limit: int
    offset: int


class UsageProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    section_code: str | None = None
    genre_code: str | None = None
    language_code: str = Field(default="en", min_length=2, max_length=16)
    register_code: str | None = None
    register_version: str | None = None
    discipline_code: str | None = None
    audience: str | None = None
    preferred_usage: Literal["general", "domain_constrained", "venue_constrained"] | None = None


class PragmaticTagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    code: str
    version: str = Field(min_length=1, max_length=32)
    strength_note: str | None = None
    context_note: str | None = None


class PhraseExampleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["positive", "negative", "revised"]
    text: str = Field(min_length=1, max_length=4000)
    explanation: str | None = None
    origin_kind: Literal["internal_original", "illustrative_synthetic", "licensed"]
    source_ref: str | None = None
    license_code: str | None = None


class MoveLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    section_code: str
    move_code: str
    relation: Literal["REALIZES_MOVE", "SUPPORTS_MOVE"] = "REALIZES_MOVE"


class StepLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    section_code: str
    move_code: str
    step_code: str
    relation: Literal["REALIZES_STEP", "SUPPORTS_STEP"] = "REALIZES_STEP"


class PhraseCaveatCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    code: str = Field(min_length=1, max_length=64)
    severity: Literal["info", "warning", "critical"] = "info"
    message: str = Field(min_length=1, max_length=4000)


class AcademicPhraseMetadataCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    function_codes: list[str] = Field(min_length=1)
    function_version: str | None = Field(default=None, min_length=1, max_length=32)
    move_links: list[MoveLinkCreate] = Field(default_factory=list)
    step_links: list[StepLinkCreate] = Field(default_factory=list)
    usage_profiles: list[UsageProfileCreate] = Field(default_factory=list)
    pragmatic_tags: list[PragmaticTagCreate] = Field(default_factory=list)
    examples: list[PhraseExampleCreate] = Field(default_factory=list)
    caveats: list[PhraseCaveatCreate] = Field(default_factory=list)
