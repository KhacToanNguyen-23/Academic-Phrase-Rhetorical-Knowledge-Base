"""Reproducible, stratified gold sentence sampling helpers."""

import math
import random
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from uuid import UUID

FILTERED_STRATUM = "FILTERED"


@dataclass(frozen=True)
class SamplingRow:
    sentence_id: UUID
    article_id: UUID
    section: str
    text: str
    # Why the mining sentence filter rejects the sentence; None when it would be mined.
    filter_reason: str | None = None


def select_sample(
    rows: list[SamplingRow],
    *,
    size: int,
    seed: int,
    max_per_article: int,
    filtered_fraction: float,
    test_fraction: float,
) -> tuple[list[SamplingRow], set[UUID]]:
    """Select deterministically and assign a test partition stratified like the sample.

    Most items come from sentences the mining filter keeps, spread evenly across sections.
    A small ``filtered_fraction`` quota comes from rejected sentences, spread across reject
    reasons, so the filter itself can be evaluated. If one pool is short, the other fills in.
    """
    if size < 1 or max_per_article < 1:
        raise ValueError("size and max_per_article must be positive")
    if not 0 <= filtered_fraction <= 1 or not 0 <= test_fraction <= 1:
        raise ValueError("fractions must be between 0 and 1")
    rng = random.Random(seed)
    kept = _groups((row for row in rows if row.filter_reason is None), key=_section, rng=rng)
    filtered = _groups(
        (row for row in rows if row.filter_reason is not None),
        key=lambda row: row.filter_reason or "",
        rng=rng,
    )
    article_counts: dict[UUID, int] = defaultdict(int)
    filtered_quota = round(size * filtered_fraction)
    selected = _round_robin(filtered, filtered_quota, article_counts, max_per_article)
    selected += _round_robin(kept, size - len(selected), article_counts, max_per_article)
    selected += _round_robin(filtered, size - len(selected), article_counts, max_per_article)
    if len(selected) < size:
        raise ValueError("not enough eligible sentences for requested sample size")
    return selected, _stratified_test_ids(selected, test_fraction, rng)


def _section(row: SamplingRow) -> str:
    return row.section or "OTHER"


def _stratum(row: SamplingRow) -> str:
    return FILTERED_STRATUM if row.filter_reason is not None else _section(row)


def _groups(
    rows: Iterable[SamplingRow], *, key: Callable[[SamplingRow], str], rng: random.Random
) -> dict[str, list[SamplingRow]]:
    groups: dict[str, list[SamplingRow]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    for name in sorted(groups):
        rng.shuffle(groups[name])
    return dict(groups)


def _round_robin(
    groups: dict[str, list[SamplingRow]],
    quota: int,
    article_counts: dict[UUID, int],
    max_per_article: int,
) -> list[SamplingRow]:
    """Take one row per group in turn until ``quota`` rows are taken or groups run dry."""
    selected: list[SamplingRow] = []
    names = sorted(groups)
    while len(selected) < quota:
        progressed = False
        for name in names:
            group = groups[name]
            while group:
                row = group.pop()
                if article_counts[row.article_id] >= max_per_article:
                    continue
                article_counts[row.article_id] += 1
                selected.append(row)
                progressed = True
                break
            if len(selected) == quota:
                break
        if not progressed:
            break
    return selected


def _stratified_test_ids(
    selected: list[SamplingRow], test_fraction: float, rng: random.Random
) -> set[UUID]:
    """Pick ``test_fraction`` of each stratum; the total is exactly round(len * fraction)."""
    strata: dict[str, list[SamplingRow]] = defaultdict(list)
    for row in selected:
        strata[_stratum(row)].append(row)
    names = sorted(strata)
    ideal = {name: len(strata[name]) * test_fraction for name in names}
    counts = {name: math.floor(ideal[name]) for name in names}
    remaining = round(len(selected) * test_fraction) - sum(counts.values())
    # Largest remainder; ties broken by name so the result is reproducible.
    for name in sorted(names, key=lambda name: (-(ideal[name] - counts[name]), name))[:remaining]:
        counts[name] += 1
    test_ids: set[UUID] = set()
    for name in names:
        test_ids.update(row.sentence_id for row in rng.sample(strata[name], counts[name]))
    return test_ids
