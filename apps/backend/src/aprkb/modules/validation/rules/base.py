"""Validation rule contracts and result types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from aprkb.modules.validation.context import ValidationContext


class Severity(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class RuleResult:
    code: str
    severity: Severity
    message: str
    span: tuple[int, int] | None = None
    applied: bool = True
    recommended_action: str | None = None


class ValidationRule(ABC):
    code: str
    requirement_id: str

    @abstractmethod
    def evaluate(self, text: str, ctx: ValidationContext) -> RuleResult: ...
