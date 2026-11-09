"""Rules intentionally outside the current sentence-validation scope."""

from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.rules.base import RuleResult, Severity, ValidationRule


class NotApplicableValidationRule(ValidationRule):
    def __init__(self, code: str, requirement_id: str, message: str) -> None:
        self.code = code
        self.requirement_id = requirement_id
        self._message = message

    def evaluate(self, text: str, ctx: ValidationContext) -> RuleResult:
        del text, ctx
        return RuleResult(
            code=self.code,
            severity=Severity.NOT_APPLICABLE,
            message=self._message,
            applied=False,
        )
