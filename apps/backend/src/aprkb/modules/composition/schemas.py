"""HTTP contracts for rendering a stored pattern version."""

from uuid import UUID

from pydantic import BaseModel, Field


class RenderRequest(BaseModel):
    recommendation_id: UUID
    pattern_version_id: UUID
    slots: dict[str, str] = Field(default_factory=dict)


class RenderResponse(BaseModel):
    pattern_version_id: UUID
    text: str
    unfilled_slots: list[str]
