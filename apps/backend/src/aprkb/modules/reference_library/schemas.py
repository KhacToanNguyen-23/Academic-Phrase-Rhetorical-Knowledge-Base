"""Public response schemas for the read-only reference library."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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


class CategoryListResponse(BaseModel):
    source: SourceNotice
    categories: list[ReferenceCategoryRead]


class HeadingGroup(BaseModel):
    heading: str
    heading_position: int
    entries: list[ReferenceEntryRead]


class CategoryDetailResponse(BaseModel):
    source: SourceNotice
    category: ReferenceCategoryRead
    headings: list[HeadingGroup]


class SearchResult(BaseModel):
    category_slug: str
    category_title: str
    heading: str
    entry: ReferenceEntryRead


class SearchResponse(BaseModel):
    source: SourceNotice
    query: str
    results: list[SearchResult]
