"""HTTP request and response schemas for recommendations."""

from uuid import UUID

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    # FR-07.1 / System Design §5.1: optional context fields are recorded and
    # handled through explicit fallback.
    intent: str | None = None
    section: str | None = None
    query: str | None = Field(default=None, max_length=500)
    move: str | None = None
    genre: str | None = None
    journal_id: UUID | None = None
    claim_type: str | None = None
    evidence_level: str | None = None
    discipline: str | None = None
    limit: int = Field(default=10, ge=1, le=100)


class ExplanationDetail(BaseModel):
    criterion: str
    value: float | None = Field(ge=0, le=1)
    weight: float = Field(ge=0, le=1)
    available: bool


class FallbackTraceEntry(BaseModel):
    tier: str
    accepted_count: int = Field(ge=0)


class RecommendationItemResponse(BaseModel):
    pattern_version_id: UUID
    canonical_frame: str
    score: float
    breakdown: dict[str, float | None]
    fallback_tier: str
    explanations: list[str]
    explanation_details: list[ExplanationDetail] = Field(default_factory=list)
    source_type: str
    version_no: int
    license_code: str | None
    license_name: str | None
    license_flag: bool
    source_reference: str | None
    article_id: UUID | None


class RecommendationResponse(BaseModel):
    items: list[RecommendationItemResponse]
    excluded: dict[str, int]
    policy_versions: dict[str, str]
    recommendation_id: UUID
    context_hash: str
    fallback_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    fallback_trace: list[FallbackTraceEntry] = Field(default_factory=list)
