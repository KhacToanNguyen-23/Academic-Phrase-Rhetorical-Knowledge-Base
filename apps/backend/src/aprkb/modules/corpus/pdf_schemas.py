"""Reviewed PDF metadata; extracted document properties are suggestions only."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from aprkb.modules.corpus.identity import normalize_doi


class PdfMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=1000)
    doi: str | None = Field(default=None, max_length=255)
    authors: list[str] = Field(default_factory=list, max_length=100)
    publication_year: int | None = Field(default=None, ge=1000, le=3000)
    journal_id: UUID | None = None
    genre_id: UUID | None = None
    source_url: HttpUrl | None = None

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title is required")
        return value.strip()

    @field_validator("doi")
    @classmethod
    def valid_doi(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        key = normalize_doi(value)
        if key is None:
            raise ValueError("Enter a DOI or doi.org URL, or leave it blank")
        return key

    @field_validator("authors")
    @classmethod
    def valid_authors(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 255 for value in values):
            raise ValueError("Each author must be nonblank and at most 255 characters")
        return [value.strip() for value in values]

    @field_validator("source_url")
    @classmethod
    def bounded_source_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and len(str(value)) > 2048:
            raise ValueError("Source URL must be at most 2048 characters")
        return value


class PdfPreview(BaseModel):
    page_count: int
    parser_version: str
    suggested_title: str | None
    suggested_authors: list[str]
    doi_candidates: list[str]
    warnings: list[str]
    duplicate: dict[str, str | None] | None
    suspected_duplicates: list[dict[str, str | None]]
    journals: list[dict[str, str]]
    genres: list[dict[str, str]]


class ArticleMetadataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    external_id: str | None
    title: str | None
    doi: str | None
    authors: list[str]
    publication_year: int | None
    journal_id: UUID | None
    genre_id: UUID | None
    source_url: str | None
    page_count: int | None
    parser_version: str | None
    metadata_provenance: dict[str, object]
    ingest_status: str
    license_id: UUID
    license_code: str | None = None
    content_sha256: str | None
    pdf_text_sha256: str | None
