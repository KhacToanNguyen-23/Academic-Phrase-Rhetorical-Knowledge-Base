"""Validation endpoint request and response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class ValidationRequest(BaseModel):
    text: str = Field(min_length=1)
    claim_type: str
    evidence_level: str
    epistemic_strength: str | None = None


class ValidationRuleResponse(BaseModel):
    code: str
    severity: str
    message: str
    span: tuple[int, int] | None


class ValidationResponse(BaseModel):
    validation_id: UUID
    severity: str
    rules: list[ValidationRuleResponse]


__all__ = ["ValidationRequest", "ValidationResponse", "ValidationRuleResponse"]
