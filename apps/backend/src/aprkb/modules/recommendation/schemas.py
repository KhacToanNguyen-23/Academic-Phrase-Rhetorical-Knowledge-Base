"""HTTP request and response schemas for recommendations."""

from uuid import UUID

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    intent: str
    section: str
    genre: str | None = None
    journal_id: UUID | None = None
    claim_type: str | None = None
    evidence_level: str | None = None
    discipline: str | None = None
    limit: int = Field(default=10, ge=1, le=100)


class RecommendationItemResponse(BaseModel):
    pattern_version_id: UUID
    canonical_frame: str
    score: float
    breakdown: dict[str, float | None]
    fallback_tier: str
    explanations: list[str]


class RecommendationResponse(BaseModel):
    items: list[RecommendationItemResponse]
    excluded: dict[str, int]
    policy_versions: dict[str, str]
    recommendation_id: UUID
