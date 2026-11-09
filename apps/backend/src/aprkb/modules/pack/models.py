"""Strict JSON contracts for Offline pack v0.1 and APB-enabled v0.2."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class FileDigest(StrictModel):
    name: Literal["patterns.json"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Counts(StrictModel):
    patterns: int = Field(ge=0)
    versions: int = Field(ge=0)
    apb_proposals: int | None = Field(default=None, ge=0)


class Manifest(StrictModel):
    pack_version: Literal["0.1", "0.2"]
    taxonomy_version: str
    producer: str = Field(min_length=1)
    created_at: datetime
    counts: Counts
    files: list[FileDigest] = Field(min_length=1, max_length=1)


class IntentPath(StrictModel):
    taxonomy_version: str
    section: str
    move: str
    step: str
    intent: str


class Slot(StrictModel):
    type: str = Field(min_length=1)
    label: str | None = None
    instruction: str | None = None
    example: str | None = None
    required: bool | None = None
    min_length: int | None = Field(default=None, ge=0)


class Usage(StrictModel):
    allowed_sections: list[str]
    allowed_genres: list[str] = Field(default_factory=list)
    evidence_min: str | None = None
    forbidden_contexts: list[str] = Field(default_factory=list)


class Variant(StrictModel):
    text: str = Field(min_length=1)
    register: str | None = None


class ArticleKey(StrictModel):
    doi: str | None = None
    source: str | None = None
    external_id: str | None = None


class Provenance(StrictModel):
    source_type: str
    author: str | None = None
    license_code: str | None = None
    article: ArticleKey | None = None
    section_code: str | None = None
    source_sentence_count: int | None = None
    occurrence_hash: str | None = None


class Review(StrictModel):
    round: int
    decision: str
    reviewer: str
    reviewer_role: str
    decided_at: datetime
    comment: str | None = None


class APBFunction(StrictModel):
    code: str = Field(min_length=1)
    version: str = Field(min_length=1)
    context_note: str | None = None


class APBMoveLink(StrictModel):
    section_code: str = Field(min_length=1)
    move_code: str = Field(min_length=1)
    relation: Literal["REALIZES_MOVE", "SUPPORTS_MOVE"] = "REALIZES_MOVE"


class APBStepLink(StrictModel):
    section_code: str = Field(min_length=1)
    move_code: str = Field(min_length=1)
    step_code: str = Field(min_length=1)
    relation: Literal["REALIZES_STEP", "SUPPORTS_STEP"] = "REALIZES_STEP"


class APBUsageProfile(StrictModel):
    section_code: str | None = None
    genre_code: str | None = None
    language_code: str = "en"
    register_code: str | None = None
    register_version: str | None = None
    discipline_code: str | None = None
    audience: str | None = None
    preferred_usage: Literal["general", "domain_constrained", "venue_constrained"] | None = None


class APBPragmaticTag(StrictModel):
    code: str = Field(min_length=1)
    version: str = Field(min_length=1)
    strength_note: str | None = None
    context_note: str | None = None


class APBExample(StrictModel):
    kind: Literal["positive", "negative", "revised"]
    text: str = Field(min_length=1)
    explanation: str | None = None
    origin_kind: Literal["internal_original", "illustrative_synthetic", "licensed"]
    source_ref: str | None = None
    license_code: str | None = None


class APBCaveat(StrictModel):
    code: str = Field(min_length=1, max_length=64)
    severity: Literal["info", "warning", "critical"] = "info"
    message: str = Field(min_length=1)


class APBMetadata(StrictModel):
    """Candidate annotations produced offline; never imply curator approval."""

    status: Literal["proposed"] = "proposed"
    function_catalog_version: str = Field(min_length=1)
    domain_catalog_version: str = Field(min_length=1)
    functions: list[APBFunction] = Field(default_factory=list)
    move_links: list[APBMoveLink] = Field(default_factory=list)
    step_links: list[APBStepLink] = Field(default_factory=list)
    usage_profiles: list[APBUsageProfile] = Field(default_factory=list)
    pragmatic_tags: list[APBPragmaticTag] = Field(default_factory=list)
    examples: list[APBExample] = Field(default_factory=list)
    caveats: list[APBCaveat] = Field(default_factory=list)


class Version(StrictModel):
    version_id: UUID
    version_no: int = Field(ge=1)
    canonical_frame: str = Field(min_length=1)
    slots: dict[str, Slot]
    claim_type: str
    epistemic_strength: str
    change_note: str | None = None
    usage: Usage
    variants: list[Variant] = Field(default_factory=list)
    provenance: Provenance
    reviews: list[Review] = Field(default_factory=list)
    apb: APBMetadata | None = None


class Pattern(StrictModel):
    pattern_id: UUID
    status: str
    intent: IntentPath
    current_version_no: int = Field(ge=1)
    versions: list[Version] = Field(min_length=1)


class Patterns(StrictModel):
    root: list[Pattern]


class PackSchema(StrictModel):
    """Combined schema exported for implementers; files are separately validated."""

    manifest: Manifest
    patterns: list[Pattern]
