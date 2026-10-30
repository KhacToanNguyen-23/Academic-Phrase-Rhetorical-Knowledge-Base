"""Pure validation pipeline."""

from dataclasses import dataclass

from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.rules.base import RuleResult, Severity, ValidationRule


@dataclass(frozen=True)
class ValidationResult:
    rules: tuple[RuleResult, ...]
    severity: Severity


class ValidationPipeline:
    def __init__(self, *, rules: list[ValidationRule]) -> None:
        self._rules = tuple(rules)

    def validate(self, text: str, context: ValidationContext) -> list[RuleResult]:
        return [rule.evaluate(text, context) for rule in self._rules]

    def run(self, text: str, context: ValidationContext) -> ValidationResult:
        results = tuple(self.validate(text, context))
        priority = {Severity.PASS: 0, Severity.WARN: 1, Severity.BLOCK: 2}
        severity = max((result.severity for result in results), key=priority.__getitem__)
        return ValidationResult(rules=results, severity=severity)
