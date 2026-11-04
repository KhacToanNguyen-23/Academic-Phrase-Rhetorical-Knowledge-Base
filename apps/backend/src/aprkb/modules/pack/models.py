"""Strict JSON contract for pack v0.1."""

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


class Manifest(StrictModel):
    pack_version: Literal["0.1"]
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
