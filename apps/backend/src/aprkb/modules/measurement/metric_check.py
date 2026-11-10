"""Deterministic catalog-term matching for measurement entries (ADR-0015).

Used by the FR-08.2 report-only check in /v1/validate and by the link proposer for
slot-less Methods patterns. It only recognises terms already in the catalog: it cannot
detect an unknown or invented measure, and it never blocks or generates content.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MetricTerms:
    """Catalog entry terms; used for every kind despite the historical name."""

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


def find_mentions(
    text: str, entries: list[MetricTerms], *, min_term_length: int
) -> list[UndeclaredMetric]:
    """Return each entry whose name or alias occurs in ``text``, with its first span."""
    found: list[UndeclaredMetric] = []
    for entry in entries:
        patterns = _usable((entry.name, *entry.terms), min_term_length)
        # Earliest mention; at the same start, the longest term ("F1 score" over "F1").
        first = min(
            (match.span() for pattern in patterns for match in pattern.finditer(text)),
            key=lambda span: (span[0], -span[1]),
            default=None,
        )
        if first is not None:
            found.append(UndeclaredMetric(entry.code, entry.name, first))
    return sorted(found, key=lambda item: item.span)


def find_undeclared_metrics(
    text: str,
    source_values: tuple[str, ...],
    metrics: list[MetricTerms],
    *,
    min_term_length: int,
) -> list[UndeclaredMetric]:
    """Return catalog metrics mentioned in ``text`` that no supplied value mentions."""
    declared = {
        item.code
        for item in find_mentions(
            "\n".join(source_values), metrics, min_term_length=min_term_length
        )
    }
    return [
        item
        for item in find_mentions(text, metrics, min_term_length=min_term_length)
        if item.code not in declared
    ]
