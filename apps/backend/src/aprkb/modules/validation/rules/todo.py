"""TODO validation rule that preserves the registry contract without inventing logic."""

from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.rules.base import RuleResult, Severity, ValidationRule


class TodoValidationRule(ValidationRule):
    def __init__(self, code: str, requirement_id: str) -> None:
        self.code = code
        self.requirement_id = requirement_id

    def evaluate(self, text: str, ctx: ValidationContext) -> RuleResult:
        del text, ctx
        # TODO(owner, PRD-6.2): implement this rule after its business criteria are approved.
        return RuleResult(
            code=self.code,
            severity=Severity.UNAVAILABLE,
            message=f"{self.code} was not evaluated",
            applied=False,
        )
