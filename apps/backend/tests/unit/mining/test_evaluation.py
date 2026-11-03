from aprkb.modules.mining.evaluation import evaluate_rows


def test_evaluator_returns_aggregate_metrics_without_surface_text() -> None:
    source_frame = "Our private fixture sentence includes a protected phrase."
    report = evaluate_rows(
        [
            {
                "expected_keep": True,
                "filter_keep": True,
                "expected_frame": source_frame,
                "predicted_frame": source_frame,
                "expected_slots": {("X", 0, 2)},
                "predicted_slots": {("X", 0, 2)},
            },
            {
                "expected_keep": False,
                "filter_keep": True,
                "expected_noise_reason": "fragment",
            },
        ],
        split="dev",
        policy_version="0.1.0",
    )

    assert report["item_count"] == 2
    assert report["sentence_filter"]["tp"] == 1
    assert report["sentence_filter"]["fp"] == 1
    assert report["sentence_filter"]["precision"] == 0.5
    assert report["sentence_filter"]["recall"] == 1
    assert source_frame not in str(report)
    assert "confusions" in report


def test_filter_and_extraction_are_scored_independently() -> None:
    clean_unextractable = {
        "expected_keep": True,
        "filter_keep": True,
        "extraction_reason": "no_reporting_verb",
    }
    failed_after_locating = {
        "expected_keep": True,
        "filter_keep": True,
        "extraction_reason": "empty_noun_phrase",
    }
    clean_extracted = {
        "expected_keep": True,
        "filter_keep": True,
        "expected_slots": {("X", 0, 2)},
        "predicted_slots": {("X", 0, 2)},
    }
    caught_noise = {
        "expected_keep": False,
        "filter_keep": False,
        "expected_noise_reason": "formula",
        "predicted_noise_reason": "math",
    }
    missed_noise = {"expected_keep": False, "filter_keep": True, "expected_noise_reason": "other"}

    report = evaluate_rows(
        [clean_unextractable, failed_after_locating, clean_extracted, caught_noise, missed_noise],
        split="dev",
        policy_version="0.1.0",
    )

    # Extraction misses do not count against the noise filter.
    assert report["sentence_filter"] == {
        "tp": 3,
        "fp": 1,
        "fn": 0,
        "tn": 1,
        "precision": 3 / 4,
        "recall": 1.0,
        "noise_reason_confusion": {"formula": {"math": 1}},
    }
    # Noise rows are excluded from extraction coverage.
    assert report["extraction"] == {
        "gold_keep_count": 3,
        "extracted_count": 1,
        "coverage": 1 / 3,
        "reasons": {
            "empty_noun_phrase": 1,
            "extracted": 1,
            "no_reporting_verb": 1,
        },
    }
    # Unextracted sentences do not distort slot scoring.
    assert report["slot_f1"] == 1.0
