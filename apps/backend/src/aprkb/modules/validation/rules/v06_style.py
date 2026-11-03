"""Warn on a provisional list of informal style phrases without NLP claims."""

import re

from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.rules.base import RuleResult, Severity, ValidationRule


class V06StyleRule(ValidationRule):
    """A deterministic phrase screen, not a grammar or coherence checker."""

    code = "V06"
    requirement_id = "PRD-6.3-V06"

    def __init__(self, phrases: list[str]) -> None:
        self._patterns = tuple(
            (phrase, re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE))
            for phrase in phrases
        )

    def evaluate(self, text: str, ctx: ValidationContext) -> RuleResult:
        del ctx
        matches = [
            (phrase, match)
            for phrase, pattern in self._patterns
            if (match := pattern.search(text)) is not None
        ]
        if not matches:
            return RuleResult(
                self.code,
                Severity.PASS,
                "No configured informal style phrases detected; grammar was not checked",
            )

        phrase, match = min(matches, key=lambda item: item[1].start())
        return RuleResult(
            code=self.code,
            severity=Severity.WARN,
            message=f"Potentially informal style phrase: '{phrase}'",
            span=match.span(),
            recommended_action="Review the wording for an appropriate academic register.",
        )
