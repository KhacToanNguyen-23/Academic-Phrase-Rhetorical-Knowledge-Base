"""HTTP contracts for recommendation feedback and validation overrides."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FeedbackMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class FeedbackCreate(BaseModel):
    recommendation_id: UUID
    pattern_version_id: UUID
    signal: Literal["accepted", "rejected", "edited"]
    payload: FeedbackMetadata | None = None


class OverrideCreate(BaseModel):
    validation_id: UUID
    rule_code: str = Field(min_length=1, max_length=32)
    rationale: str = Field(min_length=1)

    @field_validator("rationale")
    @classmethod
    def rationale_must_not_be_blank(cls, rationale: str) -> str:
        if not rationale.strip():
            raise ValueError("rationale must not be blank")
        return rationale


class CreatedRecord(BaseModel):
    id: UUID
