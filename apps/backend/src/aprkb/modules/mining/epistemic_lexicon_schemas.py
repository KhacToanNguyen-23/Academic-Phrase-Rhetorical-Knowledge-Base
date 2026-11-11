"""Admin API contracts for epistemic OOV entries and their review history."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EpistemicLexiconEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lemma: str
    pos: str
    construction_family: str
    revision: int
    tier: Literal["low", "moderate", "high", "absolute"]
    score: float
    status: Literal[
        "pending", "active", "needs_review", "policy_conflict_hold", "rejected", "superseded"
    ]
    confidence: float | None
    run1_tier: Literal["low", "moderate", "high", "absolute"] | None
    run1_confidence: float | None
    run1_rationale: str | None
    run2_tier: Literal["low", "moderate", "high", "absolute"] | None
    run2_confidence: float | None
    run2_rationale: str | None
    review_reason: str | None
    provider: str
    model: str
    prompt_version: str
    provenance: str
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EpistemicLexiconAuditRead(BaseModel):
    action: Literal["activate", "reject", "deactivate"]
    previous_status: str
    new_status: str
    created_at: datetime


class EpistemicLexiconPage(BaseModel):
    items: list[EpistemicLexiconEntryRead]
    total: int
    counts: dict[str, int]
    jobs_by_status: dict[str, int]
    failed_enrichment_jobs: int
    prompt_disagreement_entries: int
    fallback_candidate_count: int
    active_coverage: float


class EpistemicLexiconReview(BaseModel):
    action: Literal["activate", "reject", "deactivate"]
