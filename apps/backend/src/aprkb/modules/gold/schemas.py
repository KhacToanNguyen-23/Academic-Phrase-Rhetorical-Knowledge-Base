"""Request and response contracts for gold sampling."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GoldSampleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    size: int = Field(default=300, ge=1, le=1000)
    seed: int
    max_per_article: int = Field(default=100, ge=1, le=1000)


class GoldSampleResult(BaseModel):
    sample_batch: str
    count: int
    test_count: int
    status: str = "pending_ai"


class GoldLabelJobResult(BaseModel):
    job_id: UUID
    sample_batch: str
    status: str = "queued"


class GoldReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    final_labels: dict[str, object] | None = None


class GoldItemSummary(BaseModel):
    id: UUID
    sample_batch: str
    split: str
    section: str
    status: str


class GoldItemDetail(GoldItemSummary):
    ai_labels: dict[str, object] | None
    final_labels: dict[str, object] | None
    text: str
    previous_text: str | None = None
    next_text: str | None = None
    section_heading: str | None = None


class GoldReviewResult(BaseModel):
    id: UUID
    status: str
    reviewed_at: str


class GoldStats(BaseModel):
    total: int
    by_status: dict[str, int]
    by_split: dict[str, int]
    field_edits: dict[str, int]
