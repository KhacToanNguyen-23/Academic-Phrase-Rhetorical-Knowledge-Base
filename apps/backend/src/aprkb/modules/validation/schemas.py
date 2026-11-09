"""Validation endpoint request and response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class ValidationRequest(BaseModel):
    text: str = Field(min_length=1)
    claim_type: str
    evidence_level: str
    epistemic_strength: str | None = None
    context: str | None = None
    slots: dict[str, str] = Field(default_factory=dict)


class ValidationRuleResponse(BaseModel):
    code: str
    severity: str
    message: str
    span: tuple[int, int] | None
    applied: bool
    recommended_action: str | None


class MetricWarning(BaseModel):
    """FR-08.2 report-only note; never changes severity or completeness."""

    code: str
    name: str
    span: tuple[int, int]
    message: str


class ValidationResponse(BaseModel):
    validation_id: UUID
    text_hash: str
    context_hash: str
    policy_versions: dict[str, str]
    severity: str
    complete: bool
    checks_unavailable: list[str]
    checks_not_applicable: list[str]
    warnings: list[str] = Field(default_factory=list)
    rules: list[ValidationRuleResponse]
    metric_warnings: list[MetricWarning] = Field(default_factory=list)


__all__ = ["MetricWarning", "ValidationRequest", "ValidationResponse", "ValidationRuleResponse"]
