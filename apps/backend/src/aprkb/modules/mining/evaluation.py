"""Aggregate-only evaluator for human-approved gold labels."""

from collections import Counter
from typing import Any

from aprkb.modules.gold.labels import GoldLabels
from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.policies.loader import PolicyBundle


def evaluate_rows(rows: list[dict[str, Any]], *, split: str, policy_version: str) -> dict[str, Any]:
    """Score prepared prediction rows without returning sentence or frame text."""
    confusion = Counter({"tp": 0, "fp": 0, "fn": 0, "tn": 0})
    exact: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    confusions: dict[str, Counter[tuple[str, str]]] = {
        field: Counter() for field in ("section", "epistemic_strength", "tense", "ownership")
    }
    slot_counts = Counter({"tp": 0, "fp": 0, "fn": 0})
    for row in rows:
        expected_keep = bool(row["expected_keep"])
        predicted_keep = bool(row["predicted_keep"])
        confusion[
            "tp"
            if expected_keep and predicted_keep
            else "fn"
            if expected_keep
            else "fp"
            if predicted_keep
            else "tn"
        ] += 1
        if not expected_keep or not predicted_keep:
            continue
        for field in ("section", "epistemic_strength", "tense", "ownership", "frame"):
            totals[field] += 1
            actual = str(row.get(f"expected_{field}") or "unknown")
            predicted = str(row.get(f"predicted_{field}") or "unknown")
            if field in confusions:
                confusions[field][(actual, predicted)] += 1
            if row.get(f"expected_{field}") == row.get(f"predicted_{field}"):
                exact[field] += 1
        expected_slots = set(row["expected_slots"])
        predicted_slots = set(row["predicted_slots"])
        slot_counts["tp"] += len(expected_slots & predicted_slots)
        slot_counts["fp"] += len(predicted_slots - expected_slots)
        slot_counts["fn"] += len(expected_slots - predicted_slots)
    tp, fp, fn = confusion["tp"], confusion["fp"], confusion["fn"]
    slot_tp, slot_fp, slot_fn = slot_counts["tp"], slot_counts["fp"], slot_counts["fn"]
    return {
        "split": split,
        "item_count": len(rows),
        "policy_version": policy_version,
        "keep": {
            **dict(confusion),
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        },
        "accuracy": {
            field: exact[field] / totals[field] if totals[field] else None
            for field in ("section", "epistemic_strength", "tense", "ownership", "frame")
        },
        "confusions": {
            field: {
                actual: dict(
                    sorted(
                        (predicted, count)
                        for (actual_value, predicted), count in values.items()
                        if actual_value == actual
                    )
                )
                for actual in sorted({actual for actual, _ in values})
            }
            for field, values in confusions.items()
        },
        "slot_f1": (
            2 * slot_tp / (2 * slot_tp + slot_fp + slot_fn)
            if 2 * slot_tp + slot_fp + slot_fn
            else None
        ),
    }


def evaluate_approved_items(
    items: list[tuple[Any, Any, str | None, str | None]], policy: PolicyBundle, *, split: str
) -> dict[str, Any]:
    """Run the deterministic mining stages against approved items already rights-checked."""
    pipeline = MiningPipeline(stages=build_stages(policy_bundle=policy))
    rows: list[dict[str, Any]] = []
    for gold_item, sentence, previous_text, current_section in items:
        try:
            labels = GoldLabels.model_validate(gold_item.final_labels)
        except ValueError:
            raise ValueError("Approved gold labels do not match the current schema") from None
        predicted = pipeline.process(
            [
                MiningItem(
                    text=sentence.text,
                    source_sentence_ids=[sentence.id],
                    section_code=current_section,
                    char_start=sentence.char_start,
                    previous_text=previous_text,
                )
            ]
        )
        prediction = predicted[0] if predicted else None
        prediction_slots = {
            (name, start - sentence.char_start, end - sentence.char_start)
            for occurrence in (prediction.occurrences if prediction else [])
            for name, (start, end) in occurrence.slot_spans.items()
        }
        rows.append(
            {
                "expected_keep": labels.keep,
                "predicted_keep": prediction is not None,
                "expected_section": labels.section,
                "predicted_section": current_section or "OTHER",
                "expected_epistemic_strength": None
                if labels.epistemic_strength.value == "none"
                else labels.epistemic_strength.value,
                "predicted_epistemic_strength": prediction.epistemic_strength
                if prediction
                else None,
                "expected_tense": None if labels.tense.value == "none" else labels.tense.value,
                "predicted_tense": prediction.tense.value if prediction else None,
                "expected_ownership": labels.ownership.value,
                "predicted_ownership": prediction.ownership.value if prediction else None,
                "expected_frame": _normalize_frame(labels.frame),
                "predicted_frame": _normalize_frame(prediction.text if prediction else None),
                "expected_slots": {
                    (slot.name, slot.char_start, slot.char_end) for slot in labels.slots
                },
                "predicted_slots": prediction_slots,
            }
        )
    policy_version = ":".join(
        (
            policy.mining_filter.version,
            policy.reporting_verbs.version,
            policy.slot_abstraction.version,
            policy.epistemic_markers.version,
        )
    )
    return evaluate_rows(rows, split=split, policy_version=policy_version)


def _normalize_frame(value: str | None) -> str | None:
    return " ".join(value.split()).casefold() if value else None
