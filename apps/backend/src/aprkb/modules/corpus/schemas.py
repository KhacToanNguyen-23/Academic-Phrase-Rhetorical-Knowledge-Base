"""Pydantic schemas (data contracts) của module corpus."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aprkb.modules.corpus.importer import MAX_IMPORT_BATCH_LIMIT


class ArticleImportCreate(BaseModel):
    cursor: str | None = Field(default=None, max_length=1024)
    limit: int | None = Field(default=None, ge=1, le=MAX_IMPORT_BATCH_LIMIT)
    profile_id: UUID | None = None


class SlrWorkFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain_id: str | None = Field(None, alias="domainId")
    field_id: str | None = Field(None, alias="fieldId")
    subfield_id: str | None = Field(None, alias="subfieldId")
    topic_id: str | None = Field(None, alias="topicId")
    q: str | None = Field(None, max_length=200)
    doi: str | None = None
    open_alex_id: str | None = Field(None, alias="openAlexId")
    journal: str | None = None
    journal_issn: str | None = Field(None, alias="journalIssn")
    language: str | None = None
    publication_type: str | None = Field(None, alias="publicationType")
    # TODO(owner, PRD-04): confirm accepted language/publicationType values
    # and filter combination semantics with SLR.
    year_from: int | None = Field(None, ge=1000, le=3000, alias="yearFrom")
    year_to: int | None = Field(None, ge=1000, le=3000, alias="yearTo")
    has_pdf: bool | None = Field(None, alias="hasPdf")
    has_full_text: bool = Field(True, alias="hasFullText")
    has_analysis: bool | None = Field(None, alias="hasAnalysis")

    @field_validator("journal_issn")
    @classmethod
    def valid_issn(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = "".join(value.split()).replace("-", "").upper()
        if (
            len(normalized) != 8
            or not normalized[:7].isdigit()
            or not (normalized[7].isdigit() or normalized[7] == "X")
        ):
            raise ValueError("journalIssn must be a valid ISSN")
        return normalized

    @model_validator(mode="after")
    def years_order(self) -> "SlrWorkFilters":
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError("yearFrom must not exceed yearTo")
        return self

    def query_params(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for key, value in self.model_dump(by_alias=True, exclude_none=True).items():
            result[key] = str(value).lower() if isinstance(value, bool) else str(value)
        return result


ArtifactKind = Literal["FULLTEXT_MARKDOWN", "FETCHER_FULLTEXT_MARKDOWN", "SOURCE_PDF"]
DEFAULT_ARTIFACT_KINDS: tuple[ArtifactKind, ...] = (
    "FULLTEXT_MARKDOWN",
    "FETCHER_FULLTEXT_MARKDOWN",
    "SOURCE_PDF",
)


def validate_artifact_kinds(value: list[ArtifactKind]) -> list[ArtifactKind]:
    if not value or len(value) != len(set(value)):
        raise ValueError("artifact_kinds must be non-empty and unique")
    return value


class ImportProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source: Literal["slr"] = "slr"
    filters: SlrWorkFilters = Field(default_factory=lambda: SlrWorkFilters.model_validate({}))
    artifact_kinds: list[ArtifactKind] = Field(default_factory=lambda: list(DEFAULT_ARTIFACT_KINDS))
    batch_limit: int = Field(default=25, ge=1, le=MAX_IMPORT_BATCH_LIMIT)
    is_active: bool = True

    _valid_artifacts = field_validator("artifact_kinds")(validate_artifact_kinds)


class ImportProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    filters: SlrWorkFilters | None = None
    artifact_kinds: list[ArtifactKind] | None = None
    batch_limit: int | None = Field(None, ge=1, le=MAX_IMPORT_BATCH_LIMIT)
    is_active: bool | None = None

    _valid_artifacts = field_validator("artifact_kinds")(
        lambda v: validate_artifact_kinds(v) if v is not None else None
    )

    @model_validator(mode="after")
    def reject_null_patch_values(self) -> "ImportProfileUpdate":
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class ImportProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source: str
    filters: SlrWorkFilters
    artifact_kinds: list[str]
    batch_limit: int
    is_active: bool


class JobRead(BaseModel):
    id: UUID
    type: str
    status: str
    attempts: int
    error: str | None
    result: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class SlrTaxonomyItem(BaseModel):
    id: str
    label: str
    level: str
    parentId: str | None = None


class SlrTaxonomyPage(BaseModel):
    items: list[SlrTaxonomyItem]
    nextCursor: str | None
