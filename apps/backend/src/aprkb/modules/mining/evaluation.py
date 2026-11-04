"""Aggregate-only evaluator for human-approved gold labels.

Two stages are scored separately so a weakness in one cannot hide in the other:

* ``sentence_filter`` is scored on ``keep`` / ``noise_reason`` (is the sentence noise?).
* ``extraction`` is scored only on sentences gold marks ``keep=true`` and runs every stage
  after the filter, so it measures how much of the clean text the slot abstractor covers and
  how accurate the extracted fields are.
"""

from collections import Counter
from typing import Any

from aprkb.modules.gold.labels import GoldLabels
from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.modules.mining.stages.slot_abstractor import SlotAbstractor
from aprkb.nlp.features import SentenceAnalysis
from aprkb.nlp.syntax import usable_tokens
from aprkb.policies.loader import PolicyBundle

_FIELDS = ("section", "epistemic_strength", "tense", "ownership", "frame")
_EXTRACTED = "extracted"


def evaluate_rows(rows: list[dict[str, Any]], *, split: str, policy_version: str) -> dict[str, Any]:
    """Score prepared prediction rows without returning sentence or frame text."""
    confusion = Counter({"tp": 0, "fp": 0, "fn": 0, "tn": 0})
    noise_pairs: Counter[tuple[str, str]] = Counter()
    exact: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    confusions: dict[str, Counter[tuple[str, str]]] = {
        field: Counter() for field in ("section", "epistemic_strength", "tense", "ownership")
    }
    slot_counts = Counter({"tp": 0, "fp": 0, "fn": 0})
    extraction_reasons: Counter[str] = Counter()
    gold_keep_count = 0
    extracted_count = 0
    for row in rows:
        expected_keep = bool(row["expected_keep"])
        filter_keep = bool(row["filter_keep"])
        confusion[
            "tp"
            if expected_keep and filter_keep
            else "fn"
            if expected_keep
            else "fp"
            if filter_keep
            else "tn"
        ] += 1
        if not expected_keep and not filter_keep:
            noise_pairs[
                (
                    str(row.get("expected_noise_reason") or "unknown"),
                    str(row.get("predicted_noise_reason") or "unknown"),
                )
            ] += 1
        if not expected_keep:
            continue
        gold_keep_count += 1
        reason = str(row.get("extraction_reason") or _EXTRACTED)
        extraction_reasons[reason] += 1
        if reason != _EXTRACTED:
            continue
        extracted_count += 1
        for field in _FIELDS:
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
        "sentence_filter": {
            **dict(confusion),
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "noise_reason_confusion": _nested(noise_pairs),
        },
        "extraction": {
            "gold_keep_count": gold_keep_count,
            "extracted_count": extracted_count,
            "coverage": extracted_count / gold_keep_count if gold_keep_count else None,
            "reasons": dict(sorted(extraction_reasons.items())),
        },
        # Accuracy and slot F1 cover only extracted sentences; ``extraction.coverage`` is the rest.
        "accuracy": {
            field: exact[field] / totals[field] if totals[field] else None for field in _FIELDS
        },
        "confusions": {field: _nested(values) for field, values in confusions.items()},
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
    stages = build_stages(policy_bundle=policy)
    sentence_filter = next(stage for stage in stages if isinstance(stage, SentenceFilter))
    abstractor = next(stage for stage in stages if isinstance(stage, SlotAbstractor))
    downstream = MiningPipeline(stages=[s for s in stages if s is not sentence_filter])
    rows: list[dict[str, Any]] = []
    for gold_item, sentence, previous_text, current_section in items:
        try:
            labels = GoldLabels.model_validate(gold_item.final_labels)
        except ValueError:
            raise ValueError("Approved gold labels do not match the current schema") from None
        tokens = None
        if sentence.nlp_features is not None:
            try:
                tokens = usable_tokens(SentenceAnalysis.from_json(sentence.nlp_features))
            except ValueError:
                tokens = None
        mining_item = MiningItem(
            text=sentence.text,
            source_sentence_ids=[sentence.id],
            section_code=current_section,
            char_start=sentence.char_start,
            previous_text=previous_text,
            tokens=tokens,
        )
        filter_reason = sentence_filter.reject_reason(mining_item)
        row: dict[str, Any] = {
            "expected_keep": labels.keep,
            "filter_keep": filter_reason is None,
            "expected_noise_reason": labels.noise_reason.value if labels.noise_reason else None,
            "predicted_noise_reason": filter_reason,
        }
        if labels.keep:
            # The abstractor is scored in isolation: downstream stages run on every gold-keep
            # sentence, whether or not the (still basic) filter would have let it through.
            predicted = downstream.process([mining_item])
            prediction = predicted[0] if predicted else None
            row["extraction_reason"] = (
                None
                if prediction
                else abstractor.extractability_reason(sentence.text, mining_item.tokens)
            )
            row.update(_expected_fields(labels))
            row.update(_predicted_fields(prediction, sentence.char_start, current_section))
        rows.append(row)
    policy_version = ":".join(
        (
            policy.mining_filter.version,
            policy.reporting_verbs.version,
            policy.slot_abstraction.version,
            policy.epistemic_markers.version,
        )
    )
    return evaluate_rows(rows, split=split, policy_version=policy_version)


def _expected_fields(labels: GoldLabels) -> dict[str, Any]:
    return {
        "expected_section": labels.section,
        "expected_epistemic_strength": None
        if labels.epistemic_strength.value == "none"
        else labels.epistemic_strength.value,
        "expected_tense": None if labels.tense.value == "none" else labels.tense.value,
        "expected_ownership": labels.ownership.value,
        "expected_frame": _normalize_frame(labels.frame),
        "expected_slots": {(slot.name, slot.char_start, slot.char_end) for slot in labels.slots},
    }


def _predicted_fields(
    prediction: MiningItem | None, sentence_start: int, current_section: str | None
) -> dict[str, Any]:
    slots = {
        (name, start - sentence_start, end - sentence_start)
        for occurrence in (prediction.occurrences if prediction else [])
        for name, (start, end) in occurrence.slot_spans.items()
    }
    return {
        "predicted_section": current_section or "OTHER",
        "predicted_epistemic_strength": prediction.epistemic_strength if prediction else None,
        "predicted_tense": prediction.tense.value if prediction else None,
        "predicted_ownership": prediction.ownership.value if prediction else None,
        "predicted_frame": _normalize_frame(prediction.text if prediction else None),
        "predicted_slots": slots,
    }


def _nested(values: Counter[tuple[str, str]]) -> dict[str, dict[str, int]]:
    return {
        actual: dict(
            sorted(
                (predicted, count)
                for (actual_value, predicted), count in values.items()
                if actual_value == actual
            )
        )
        for actual in sorted({actual for actual, _ in values})
    }


def _normalize_frame(value: str | None) -> str | None:
    return " ".join(value.split()).casefold() if value else None
