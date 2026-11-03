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


class RenderValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str
    type: str | None = None


class RenderErrorDetails(BaseModel):
    field_errors: dict[str, str] | None = None
    errors: list[RenderValidationIssue] | None = None


class RenderError(BaseModel):
    code: str
    message: str
    details: RenderErrorDetails | None = None


class RenderErrorResponse(BaseModel):
    error: RenderError
    request_id: str
