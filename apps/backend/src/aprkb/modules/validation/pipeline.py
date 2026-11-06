"""Pure validation pipeline."""

from dataclasses import dataclass

from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.rules.base import RuleResult, Severity, ValidationRule


@dataclass(frozen=True)
class ValidationResult:
    rules: tuple[RuleResult, ...]
    severity: Severity
    complete: bool


class ValidationPipeline:
    def __init__(self, *, rules: list[ValidationRule]) -> None:
        self._rules = tuple(rules)

    def validate(self, text: str, context: ValidationContext) -> list[RuleResult]:
        return [rule.evaluate(text, context) for rule in self._rules]

    def run(self, text: str, context: ValidationContext) -> ValidationResult:
        # Unavailable in-scope rules make the result incomplete. Rules outside
        # sentence-validation scope do not count as missing checks.
        results = tuple(self.validate(text, context))
        priority = {
            Severity.NOT_APPLICABLE: -2,
            Severity.UNAVAILABLE: -1,
            Severity.PASS: 0,
            Severity.WARN: 1,
            Severity.BLOCK: 2,
        }
        evaluated = [
            result.severity for result in results if result.severity is not Severity.NOT_APPLICABLE
        ]
        severity = max(evaluated, key=priority.__getitem__, default=Severity.PASS)
        return ValidationResult(
            rules=results,
            severity=severity,
            complete=all(
                result.applied or result.severity is Severity.NOT_APPLICABLE for result in results
            ),
        )
