"""FR-08.2 report-only check: catalog metrics named in text but not in the writer's context.

This only recognises metrics already in the catalog. It cannot detect an unknown or
invented metric name, and it never blocks validation or generates evidence.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MetricTerms:
    code: str
    name: str
    terms: tuple[str, ...]


@dataclass(frozen=True)
class UndeclaredMetric:
    code: str
    name: str
    span: tuple[int, int]


def _pattern(term: str) -> re.Pattern[str]:
    # Acronyms such as "ACC" or "RMSE" match case-sensitively so ordinary words do not.
    flags = 0 if term.isupper() else re.IGNORECASE
    return re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", flags)


def _usable(terms: tuple[str, ...], min_length: int) -> list[re.Pattern[str]]:
    unique = {term.strip() for term in terms if len(term.strip()) >= min_length}
    return [_pattern(term) for term in sorted(unique)]


def find_undeclared_metrics(
    text: str,
    source_values: tuple[str, ...],
    metrics: list[MetricTerms],
    *,
    min_term_length: int,
) -> list[UndeclaredMetric]:
    """Return catalog metrics mentioned in ``text`` that no supplied value mentions."""
    supplied = "\n".join(source_values)
    found: list[UndeclaredMetric] = []
    for metric in metrics:
        patterns = _usable((metric.name, *metric.terms), min_term_length)
        # Earliest mention; at the same start, the longest term ("F1 score" over "F1").
        first = min(
            (match.span() for pattern in patterns for match in pattern.finditer(text)),
            key=lambda span: (span[0], -span[1]),
            default=None,
        )
        if first is None:
            continue
        if any(pattern.search(supplied) for pattern in patterns):
            continue
        found.append(UndeclaredMetric(metric.code, metric.name, first))
    return sorted(found, key=lambda item: item.span)
