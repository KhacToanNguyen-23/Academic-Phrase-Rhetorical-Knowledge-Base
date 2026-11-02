"""Detect epistemic markers stronger than the evidence policy permits."""

import re

from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.rules.base import RuleResult, Severity, ValidationRule
from aprkb.policies.evidence import EvidencePolicy
from aprkb.policies.schemas import EpistemicMarkersPolicy

_NON_INFLECTING_MARKERS = frozenset({"always", "could", "is likely", "may", "might", "possibly"})
_IRREGULAR_VERB_FORMS = {
    "prove": ("proven",),
    "show": ("shown",),
}


class V02ClaimEvidenceRule(ValidationRule):
    """FR-08.1 / BR-03: enforce evidence-supported wording strength."""

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
            recommended_action="Use a weaker claim marker or supply supporting evidence.",
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

    @classmethod
    def _marker_pattern(cls, marker: str) -> re.Pattern[str]:
        folded = marker.casefold()
        alternatives = (
            [folded] if folded in _NON_INFLECTING_MARKERS else cls._inflected_forms(folded)
        )
        escaped = "|".join(
            re.escape(alternative) for alternative in sorted(alternatives, key=len, reverse=True)
        )
        if marker[0].isalnum():
            escaped = rf"(?<!\w)(?:{escaped})"
        if marker[-1].isalnum():
            escaped = rf"{escaped}(?!\w)"
        return re.compile(escaped)

    @classmethod
    def _inflected_forms(cls, marker: str) -> list[str]:
        head, separator, rest = marker.partition(" ")
        forms = cls._verb_forms(cls._verb_base(head))
        if not separator:
            return list(forms)
        return [f"{form} {rest}" for form in forms]

    @staticmethod
    def _verb_base(word: str) -> str:
        if word.endswith("ies") and len(word) > 3:
            return f"{word[:-3]}y"
        if word.endswith(("ches", "shes", "xes", "zes", "ses", "oes")):
            return word[:-2]
        if word.endswith("s") and not word.endswith("ss"):
            return word[:-1]
        return word

    @staticmethod
    def _verb_forms(base: str) -> tuple[str, ...]:
        if base.endswith(("s", "x", "z", "ch", "sh", "o")):
            third_person = f"{base}es"
        elif base.endswith("y") and len(base) > 1 and base[-2] not in "aeiou":
            third_person = f"{base[:-1]}ies"
        else:
            third_person = f"{base}s"
        if base.endswith("e"):
            past = f"{base}d"
            gerund = f"{base[:-1]}ing"
        else:
            past = f"{base}ed"
            gerund = f"{base}ing"
        forms = {base, third_person, past, gerund}
        forms.update(_IRREGULAR_VERB_FORMS.get(base, ()))
        return tuple(sorted(forms, key=len, reverse=True))

    @classmethod
    def _contains_marker(cls, text: str, marker: str) -> bool:
        return cls._marker_pattern(marker).search(text) is not None
