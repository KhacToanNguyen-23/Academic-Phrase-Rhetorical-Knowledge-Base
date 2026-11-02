from collections import Counter
from uuid import uuid4

import pytest

from aprkb.modules.gold.sampling import SamplingRow, select_sample


def _rows(sections: dict[str, int], *, reasons: dict[str, int] | None = None) -> list[SamplingRow]:
    articles = (uuid4(), uuid4(), uuid4())
    rows = [
        SamplingRow(uuid4(), articles[i % 3], section, f"mock sentence {i}")
        for section, count in sections.items()
        for i in range(count)
    ]
    rows += [
        SamplingRow(uuid4(), articles[i % 3], "REFERENCES", f"mock noise {i}", filter_reason=reason)
        for reason, count in (reasons or {}).items()
        for i in range(count)
    ]
    return rows


def _sample(rows: list[SamplingRow], size: int, **overrides: float):  # type: ignore[no-untyped-def]
    options = {"filtered_fraction": 0.10, "test_fraction": 0.30, **overrides}
    return select_sample(rows, size=size, seed=741, max_per_article=1000, **options)


def test_sampling_is_deterministic_and_assigns_exact_test_fraction():
    rows = _rows({"INTRO": 100, "RESULTS": 100}, reasons={"length": 50})
    first, test_ids = _sample(rows, 30)
    second, second_test_ids = _sample(rows, 30)
    assert [row.sentence_id for row in first] == [row.sentence_id for row in second]
    assert test_ids == second_test_ids
    assert len(test_ids) == 9


def test_filtered_sentences_only_fill_their_quota_spread_across_reasons():
    rows = _rows({"INTRO": 100, "RESULTS": 100}, reasons={"excluded_section": 200, "caption": 50})
    sample, _ = _sample(rows, 100)

    assert Counter(row.filter_reason for row in sample) == {
        None: 90,
        "excluded_section": 5,
        "caption": 5,
    }
    assert Counter(row.section for row in sample if row.filter_reason is None) == {
        "INTRO": 45,
        "RESULTS": 45,
    }


def test_short_filtered_pool_is_filled_from_kept_sentences_and_vice_versa():
    sample, _ = _sample(_rows({"INTRO": 50}, reasons={"math": 2}), 40)
    assert Counter(row.filter_reason for row in sample) == {None: 38, "math": 2}

    sample, _ = _sample(_rows({"INTRO": 5}, reasons={"math": 50}), 20)
    assert Counter(row.filter_reason for row in sample) == {None: 5, "math": 15}


def test_test_split_is_stratified_by_section():
    rows = _rows({"INTRO": 100, "METHODS": 100, "RESULTS": 100}, reasons={"length": 100})
    sample, test_ids = _sample(rows, 100)
    test_by_stratum = Counter(
        "FILTERED" if row.filter_reason else row.section
        for row in sample
        if row.sentence_id in test_ids
    )

    assert sum(test_by_stratum.values()) == 30
    assert test_by_stratum == {"INTRO": 9, "METHODS": 9, "RESULTS": 9, "FILTERED": 3}


def test_sampling_respects_article_cap():
    article = uuid4()
    rows = [SamplingRow(uuid4(), article, "RESULTS", f"mock {i}") for i in range(20)]
    with pytest.raises(ValueError, match="not enough"):
        select_sample(
            rows, size=4, seed=2, max_per_article=3, filtered_fraction=0.1, test_fraction=0.3
        )
    sample, _ = select_sample(
        rows, size=3, seed=2, max_per_article=3, filtered_fraction=0.1, test_fraction=0.3
    )
    assert len(sample) == 3
