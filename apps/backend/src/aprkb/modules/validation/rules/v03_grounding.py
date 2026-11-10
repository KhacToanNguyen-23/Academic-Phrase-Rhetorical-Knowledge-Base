"""Block numeric and bibliographic details absent from writer-provided values."""

import re

from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.rules.base import RuleResult, Severity, ValidationRule

# A number ends at a word character or at a decimal point that is followed by a digit.
# A sentence-final period ("was 0.0111.") must not hide the number from the check.
NUMBER_END = r"(?!\w)(?!\.\d)"

DETAIL_PATTERNS = (
    ("DOI", re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)),
    (
        "citation",
        re.compile(r"\([A-Z][A-Za-z'’\-]+(?:\s+et\s+al\.)?,\s*\d{4}[a-z]?\)"),
    ),
    (
        "numeric claim",
        re.compile(
            r"(?<![\w.])(?:p\s*[<=>]\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?)" + NUMBER_END,
            re.IGNORECASE,
        ),
    ),
)


class V03GroundingRule(ValidationRule):
    """Deterministic guard for numbers, DOI, and parenthetical citations."""

    code = "V03"
    requirement_id = "PRD-6.2-V03"

    def __init__(self, severity: Severity) -> None:
        self._severity = severity

    def evaluate(self, text: str, ctx: ValidationContext) -> RuleResult:
        supplied = " ".join(ctx.source_values).casefold()
        unsupported: list[tuple[str, tuple[int, int]]] = []
        for kind, pattern in DETAIL_PATTERNS:
            for match in pattern.finditer(text):
                value = self._normalize(match.group())
                if value and not self._is_supported(kind, value, supplied):
                    unsupported.append((kind, match.span()))
        if not unsupported:
            return RuleResult(
                self.code,
                Severity.PASS,
                "No unsupported numeric or bibliographic details detected",
            )

        kind, span = min(unsupported, key=lambda item: item[1][0])
        return RuleResult(
            code=self.code,
            severity=self._severity,
            message=f"A {kind} is not present in the supplied slots or context",
            span=span,
            recommended_action=(
                "Remove the detail or add it to the writer-provided supporting context."
            ),
        )

    @staticmethod
    def _normalize(value: str) -> str:
        # Remove space around comparators and before "%", but keep the space after "%"
        # so that "95% CI" does not collapse into "95%ci" and hide the "95%".
        compact = re.sub(r"\s*([<=>])\s*", r"\1", value)
        compact = re.sub(r"\s*%", "%", compact)
        return re.sub(r"\s+", " ", compact).strip().rstrip(".,;:").casefold()

    @classmethod
    def _is_supported(cls, kind: str, value: str, supplied: str) -> bool:
        normalized_source = cls._normalize(supplied)
        if kind == "numeric claim":
            return (
                re.search(rf"(?<![\w.]){re.escape(value)}{NUMBER_END}", normalized_source)
                is not None
            )
        return (
            re.search(rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])", normalized_source)
            is not None
        )
