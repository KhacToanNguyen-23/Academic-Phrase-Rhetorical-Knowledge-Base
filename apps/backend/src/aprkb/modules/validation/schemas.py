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
    applied: bool
    recommended_action: str | None


class ValidationResponse(BaseModel):
    validation_id: UUID
    text_hash: str
    context_hash: str
    policy_versions: dict[str, str]
    severity: str
    complete: bool
    checks_unavailable: list[str]
    rules: list[ValidationRuleResponse]


__all__ = ["ValidationRequest", "ValidationResponse", "ValidationRuleResponse"]
