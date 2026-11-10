"""Pydantic contracts for frame-label review and approval."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CandidateLabelRead(BaseModel):
    label_code: str
    value: Any | None
    status: Literal["proposed", "confirmed", "rejected"]
    source: str
    confidence: float | None
    options: list[dict[str, Any]] | None
    evidence: list[dict[str, Any]] | None
    needs_attention: bool
    agreement: str | None
    reviewer_id: UUID | None
    reviewed_at: datetime | None


class FrameLabelReviewRead(BaseModel):
    candidate_id: UUID
    canonical_frame: str
    family: str
    paper_count: int
    labels: list[CandidateLabelRead]


class FrameLabelReviewPage(BaseModel):
    items: list[FrameLabelReviewRead]
    total: int


class FrameLabelDecision(BaseModel):
    candidate_id: UUID
    label_code: str
    decision: Literal["approve", "edit", "reject"]
    value: str | None = None


class BulkFrameLabelReviewCreate(BaseModel):
    decisions: list[FrameLabelDecision] = Field(min_length=1, max_length=200)


class BulkFrameLabelReviewResult(BaseModel):
    decisions_applied: int
    reviewed_at: datetime
