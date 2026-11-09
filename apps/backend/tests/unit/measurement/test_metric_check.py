"""FR-08.2 report-only metric check (ADR-0015)."""

from aprkb.modules.measurement.metric_check import MetricTerms, find_undeclared_metrics

METRICS = [
    MetricTerms("accuracy", "Accuracy", ("ACC",)),
    MetricTerms("f1_score", "F1 score", ("F1", "F-measure")),
    MetricTerms("mean_score", "Mean score", ("M",)),
    MetricTerms("cohens_kappa", "Cohen's kappa", ("kappa",)),
]


def check(text: str, *supplied: str) -> list[tuple[str, tuple[int, int]]]:
    return [
        (item.code, item.span)
        for item in find_undeclared_metrics(text, supplied, METRICS, min_term_length=2)
    ]


def test_metric_absent_from_context_is_reported_with_first_span():
    text = "The model reached an F1 score of 0.81 and high accuracy."
    assert check(text) == [("f1_score", (21, 29)), ("accuracy", (47, 55))]


def test_metric_declared_through_any_alias_is_not_reported():
    assert check("Accuracy improved.", "we report ACC on the test split") == []
    assert check("The F-measure rose.", "F1 score") == []


def test_acronyms_are_case_sensitive_and_word_bounded():
    assert check("The acc value and ACCURACY.") == [("accuracy", (18, 26))]
    assert check("The ACCx tool and F1-like curve.") == []


def test_short_terms_below_minimum_are_ignored():
    assert check("Smith, M. reported the result.") == []


def test_no_catalog_or_no_mention_gives_no_warning():
    assert find_undeclared_metrics("Accuracy rose.", (), [], min_term_length=2) == []
    assert check("Participants completed the task.") == []
