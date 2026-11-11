"""API schemas for the Metric & Measurement catalog."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["metric", "method", "protocol"]
LinkStatus = Literal["proposed", "approved", "rejected"]


class MeasurementSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    kind: Kind
    name: str
    aliases: list[str]
    definition: str


class MeasurementListResponse(BaseModel):
    catalog_version: str | None
    items: list[MeasurementSummary]
    total: int


class RelatedMeasurement(BaseModel):
    relation: str
    direction: Literal["outgoing", "incoming"]
    code: str
    kind: Kind
    name: str


LinkOrigin = Literal["manual", "term_match"]


class SlotLinkRead(BaseModel):
    id: UUID
    entry_code: str
    pattern_id: UUID
    canonical_frame: str | None
    slot_name: str | None = Field(description="None for a pattern-level link.")
    origin: LinkOrigin
    review_status: LinkStatus
    note: str | None
    created_at: datetime
    reviewed_at: datetime | None


class MeasurementDetail(MeasurementSummary):
    formula: str | None
    scale: str | None
    value_range: str | None
    usage_note: str | None
    example: str | None
    catalog_version: str
    related: list[RelatedMeasurement]
    slot_links: list[SlotLinkRead] = Field(
        description="Approved links only; each entry is a suggestion, never an auto-filled value."
    )


class SlotSuggestion(BaseModel):
    code: str
    kind: Kind
    name: str
    example: str | None


class SlotSuggestionsResponse(BaseModel):
    pattern_id: UUID
    slot_name: str
    items: list[SlotSuggestion]
    notice: str = "Suggestions only. The writer must choose and phrase the slot value."


class MeasurementImportResult(BaseModel):
    status: Literal["imported", "unchanged"]
    catalog_version: str
    entries_created: int
    entries_updated: int
    relations: int
    missing_codes: list[str] = Field(
        description="Codes stored earlier but absent from this catalog; kept, not deleted."
    )


class SlotLinkProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_code: str = Field(min_length=1, max_length=64)
    pattern_id: UUID
    slot_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Omit for a pattern-level link (the pattern describes this measure).",
    )
    note: str | None = Field(default=None, max_length=1000)


class SlotLinkReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class SlotLinkListResponse(BaseModel):
    items: list[SlotLinkRead]


class RelatedMeasurementForPattern(BaseModel):
    code: str
    kind: Kind
    name: str
    definition: str
    slot_name: str | None


class PatternMeasurementsResponse(BaseModel):
    pattern_id: UUID
    items: list[RelatedMeasurementForPattern]
