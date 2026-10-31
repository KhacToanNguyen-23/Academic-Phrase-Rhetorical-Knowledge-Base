"""Detect epistemic markers stronger than the evidence policy permits."""

import re

from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.rules.base import RuleResult, Severity, ValidationRule
from aprkb.policies.evidence import EvidencePolicy
from aprkb.policies.schemas import EpistemicMarkersPolicy


class V02ClaimEvidenceRule(ValidationRule):
    code = "V02"
    requirement_id = "PRD-6.2-V02"

    def __init__(
        self,
        *,
        evidence_policy: EvidencePolicy,
        lexicon: EpistemicMarkersPolicy,
        severity: Severity,
    ) -> None:
        self._evidence_policy = evidence_policy
        self._lexicon = lexicon
        self._severity = severity

    def evaluate(self, text: str, ctx: ValidationContext) -> RuleResult:
        found = self._strongest_marker(text)
        if found is None or self._evidence_policy.is_allowed(
            ctx.claim_type, ctx.evidence_level, found
        ):
            return RuleResult(self.code, Severity.PASS, "Claim strength is supported by evidence")
        marker, span = self._marker_span(text, found)
        return RuleResult(
            code=self.code,
            severity=self._severity,
            message=f"The marker '{marker}' exceeds the evidence-supported claim strength",
            span=span,
        )

    def _strongest_marker(self, text: str) -> str | None:
        folded = text.casefold()
        strength_order = self._evidence_policy.strength_order
        matched = [
            strength
            for strength, markers in self._lexicon.markers.items()
            if any(self._contains_marker(folded, marker) for marker in markers)
        ]
        return (
            max(matched, key=lambda strength: strength_order.get(strength, float("inf")))
            if matched
            else None
        )

    def _marker_span(self, text: str, strength: str) -> tuple[str, tuple[int, int]]:
        folded = text.casefold()
        for marker in self._lexicon.markers[strength]:
            match = self._marker_pattern(marker).search(folded)
            if match is not None:
                return text[match.start() : match.end()], match.span()
        return strength, (0, len(text))

    @staticmethod
    def _marker_pattern(marker: str) -> re.Pattern[str]:
        escaped = re.escape(marker.casefold())
        if marker[0].isalnum():
            escaped = rf"(?<!\w){escaped}"
        if marker[-1].isalnum():
            escaped = rf"{escaped}s?(?!\w)"
        return re.compile(escaped)

    @classmethod
    def _contains_marker(cls, text: str, marker: str) -> bool:
        return cls._marker_pattern(marker).search(text) is not None
