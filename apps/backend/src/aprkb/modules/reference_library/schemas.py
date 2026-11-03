"""Public response schemas for the read-only reference library."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceNotice(BaseModel):
    name: str
    url: str
    license_status: str
    rights_status: str
    notice: str


class ReferenceEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    heading: str
    heading_position: int
    block_index: int
    block_id: str | int
    kind: Literal["note", "phrase"]
    text: str | None
    cells: list[list[str]] | None
    position: int


class ReferenceCategoryRead(BaseModel):
    slug: str
    title: str
    kind: Literal["section", "function"]
    position: int
    entry_count: int
    unmapped_entry_count: int
    unmapped_section_entry_count: int
    unmapped_intent_entry_count: int
    source_url: str
    resolved_url: str
    captured_at: str
    html_sha256: str
    source_category: str
    license_status: str
    rights_status: str
    status: str
    note: str
    extraction_method: str | None
    section_code: str | None = None
    general_function_code: str | None = None
    intent_codes: list[str] = Field(default_factory=list)
    review_status: str | None = None


class CategoryListResponse(BaseModel):
    source: SourceNotice | None
    categories: list[ReferenceCategoryRead]


class HeadingGroup(BaseModel):
    heading: str
    heading_position: int
    entries: list[ReferenceEntryRead]
    intent_code: str | None = None
    review_status: str | None = None


class CategoryDetailResponse(BaseModel):
    source: SourceNotice | None
    category: ReferenceCategoryRead
    headings: list[HeadingGroup]


class SearchResult(BaseModel):
    category_slug: str
    category_title: str
    heading: str
    entry: ReferenceEntryRead
    section_code: str | None = None
    intent_code: str | None = None
    review_status: str | None = None


class SearchResponse(BaseModel):
    source: SourceNotice | None
    query: str
    results: list[SearchResult]
