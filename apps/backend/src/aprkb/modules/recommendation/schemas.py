"""HTTP request and response schemas for recommendations."""

from uuid import UUID

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    # FR-07.1 / System Design §5.1: optional context fields are recorded and
    # handled through explicit fallback.
    intent: str
    section: str
    query: str | None = Field(default=None, max_length=500)
    move: str | None = None
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
    source_type: str
    version_no: int
    license_code: str | None
    license_name: str | None
    source_reference: str | None


class RecommendationResponse(BaseModel):
    items: list[RecommendationItemResponse]
    excluded: dict[str, int]
    policy_versions: dict[str, str]
    recommendation_id: UUID
    context_hash: str
    fallback_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
