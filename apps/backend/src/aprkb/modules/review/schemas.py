"""HTTP contracts for candidate review queue and decisions."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from aprkb.modules.mining.schemas import SlotDefinition


class CandidateSummary(BaseModel):
    id: UUID
    canonical_frame: str
    slots: dict[str, SlotDefinition]
    intent_id: UUID | None
    confidence: float | None
    epistemic_strength: str | None
    source_sentence_ids: list[UUID]
    status: str


class ReviewDecisionCreate(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=4000)


class ReviewDecisionResult(BaseModel):
    candidate_id: UUID
    round: int
    decision: str
    candidate_status: str
    pattern_version_id: UUID | None
