from aprkb.modules.mining.evaluation import evaluate_rows


def test_evaluator_returns_aggregate_metrics_without_surface_text() -> None:
    source_frame = "Our private fixture sentence includes a protected phrase."
    report = evaluate_rows(
        [
            {
                "expected_keep": True,
                "predicted_keep": True,
                "expected_frame": source_frame,
                "predicted_frame": source_frame,
                "expected_slots": {("X", 0, 2)},
                "predicted_slots": {("X", 0, 2)},
            },
            {
                "expected_keep": False,
                "predicted_keep": True,
                "expected_slots": set(),
                "predicted_slots": set(),
            },
        ],
        split="dev",
        policy_version="0.1.0",
    )

    assert report["item_count"] == 2
    assert report["keep"]["tp"] == 1
    assert report["keep"]["fp"] == 1
    assert report["keep"]["precision"] == 0.5
    assert report["keep"]["recall"] == 1
    assert source_frame not in str(report)
    assert "confusions" in report
