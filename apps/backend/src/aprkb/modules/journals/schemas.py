"""HTTP schemas for journal profiles and cached guideline writes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JournalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    issn: str | None
    publisher: str | None
    field: str | None
    subfield: str | None
    similar_journal_ids: list[UUID]


class GuidelineCreate(BaseModel):
    rule_type: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)
    is_mandatory: bool = False
    active_from: datetime | None = None
    active_to: datetime | None = None


class GuidelineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    journal_id: UUID
    rule_type: str
    payload: dict[str, Any]
    is_mandatory: bool
