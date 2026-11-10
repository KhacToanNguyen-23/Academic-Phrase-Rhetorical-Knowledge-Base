"""Deterministic merge of two independent AI label passes and rule anchors."""

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any
from uuid import UUID

from aprkb.modules.mining.labelers import (
    AI_LABEL_FIELDS,
    FrameLabelOutput,
    ProposedFrameLabel,
    vocabulary_codes,
)
from aprkb.policies.schemas import FrameLabelVocabularyPolicy


@dataclass(frozen=True)
class MergedFrameLabel:
    label_code: str
    value: str | None
    status: str
    source: str
    confidence: float | None
    options: list[dict[str, Any]]
    needs_attention: bool
    agreement: str
    evidence: list[dict[str, str | None]] = dataclass_field(default_factory=list)


def merge_frame_labels(
    *,
    candidate_id: UUID,
    pass_a: FrameLabelOutput | None,
    pass_b: FrameLabelOutput | None,
    anchors: dict[str, str],
    vocabulary: FrameLabelVocabularyPolicy,
) -> list[MergedFrameLabel]:
    """Merge code-only model output while preserving disagreement and hierarchy warnings."""
    if pass_a is not None and pass_a.candidate_id != candidate_id:
        raise ValueError("Pass A candidate id does not match the frame")
    if pass_b is not None and pass_b.candidate_id != candidate_id:
        raise ValueError("Pass B candidate id does not match the frame")

    valid_codes = vocabulary_codes(vocabulary)
    values_a = _values(pass_a, valid_codes)
    values_b = _values(pass_b, valid_codes)
    issues = [
        *_hierarchy_issues(values_a, vocabulary),
        *_hierarchy_issues(values_b, vocabulary),
    ]

    merged: list[MergedFrameLabel] = []
    for field in AI_LABEL_FIELDS:
        a = values_a[field]
        b = values_b[field]
        anchor = anchors.get(field)
        item = _merge_one(field, a, b)
        if anchor is not None and item.value not in {None, "unclear", anchor}:
            item = MergedFrameLabel(
                **{
                    **item.__dict__,
                    "needs_attention": True,
                    "options": [*item.options, {"source": "anchor", "value": anchor}],
                }
            )
        if field in issues:
            item = MergedFrameLabel(
                **{
                    **item.__dict__,
                    "needs_attention": True,
                    "options": [*item.options, {"reason": "hierarchy_mismatch"}],
                }
            )
        merged.append(item)
    return merged


def _values(
    output: FrameLabelOutput | None,
    valid_codes: dict[str, list[str]],
) -> dict[str, ProposedFrameLabel]:
    values = output.labels if output is not None else {}
    return {
        field: label
        if (label := values.get(field)) is not None
        and (label.value is None or label.value in valid_codes[field])
        else ProposedFrameLabel(value="unclear", confidence=None, evidence=None)
        for field in AI_LABEL_FIELDS
    }


def _merge_one(field: str, a: ProposedFrameLabel, b: ProposedFrameLabel) -> MergedFrameLabel:
    value_a = a.value or "unclear"
    value_b = b.value or "unclear"
    if value_a == value_b:
        return MergedFrameLabel(
            label_code=field,
            value=value_a,
            status="proposed",
            source="ai:2pass",
            confidence=_lower_confidence(a.confidence, b.confidence),
            options=[],
            needs_attention=False,
            agreement="both_agree",
            evidence=[{"pass": "a", "text": a.evidence}, {"pass": "b", "text": b.evidence}],
        )
    confident_a = value_a not in {"unclear", "none_of_these"} and a.confidence is not None
    confident_b = value_b not in {"unclear", "none_of_these"} and b.confidence is not None
    agreement = "only_one_confident" if confident_a != confident_b else "disagree"
    return MergedFrameLabel(
        label_code=field,
        value=None,
        status="proposed",
        source="ai:2pass",
        confidence=None,
        options=[
            {"pass": "a", "value": value_a, "confidence": a.confidence, "evidence": a.evidence},
            {"pass": "b", "value": value_b, "confidence": b.confidence, "evidence": b.evidence},
        ],
        needs_attention=True,
        agreement=agreement,
        evidence=[{"pass": "a", "text": a.evidence}, {"pass": "b", "text": b.evidence}],
    )


def _lower_confidence(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return min(a, b)


def _hierarchy_issues(
    values: dict[str, ProposedFrameLabel], vocabulary: FrameLabelVocabularyPolicy
) -> set[str]:
    intent_step = {entry.code: entry.parent for entry in vocabulary.intents}
    step_move = {entry.code: entry.parent for entry in vocabulary.steps}
    move_group = {entry.code: entry.parent for entry in vocabulary.moves}
    group = values["function_group"].value
    move = values["move"].value
    step = values["step"].value
    intent = values["intent"].value
    issues: set[str] = set()
    if intent not in {None, "unclear", "none_of_these"}:
        expected_step = intent_step.get(intent)
        expected_move = step_move.get(expected_step or "")
        expected_group = move_group.get(expected_move or "")
        if step not in {None, "unclear", "none_of_these"} and step != expected_step:
            issues.update({"intent", "step"})
        if move not in {None, "unclear", "none_of_these"} and move != expected_move:
            issues.update({"intent", "move"})
        if group not in {None, "unclear", "none_of_these"} and group != expected_group:
            issues.update({"intent", "function_group"})
    if (
        move not in {None, "unclear", "none_of_these"}
        and group
        not in {
            None,
            "unclear",
            "none_of_these",
        }
        and move_group.get(move) != group
    ):
        issues.update({"function_group", "move"})
    if (
        step not in {None, "unclear", "none_of_these"}
        and move
        not in {
            None,
            "unclear",
            "none_of_these",
        }
        and step_move.get(step) != move
    ):
        issues.update({"move", "step"})
    if (
        intent not in {None, "unclear", "none_of_these"}
        and step
        not in {
            None,
            "unclear",
            "none_of_these",
        }
        and intent_step.get(intent) != step
    ):
        issues.update({"step", "intent"})
    return issues
