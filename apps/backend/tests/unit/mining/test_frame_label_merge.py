from uuid import UUID, uuid4

from aprkb.modules.mining.label_merge import merge_frame_labels
from aprkb.modules.mining.labelers import FrameLabelOutput, ProposedFrameLabel
from aprkb.policies.loader import load_policy_bundle


def _output(
    candidate_id: UUID,
    *,
    intent: str = "report_finding",
    group: str = "REPORTING_RESULTS",
    move: str = "present_outcomes",
    step: str = "state_evidence",
) -> FrameLabelOutput:
    return FrameLabelOutput(
        candidate_id=candidate_id,
        labels={
            "function_group": ProposedFrameLabel(
                value=group, confidence=0.9, evidence="Reports an outcome"
            ),
            "move": ProposedFrameLabel(value=move, confidence=0.8, evidence="Presents outcomes"),
            "step": ProposedFrameLabel(value=step, confidence=0.7, evidence="States evidence"),
            "intent": ProposedFrameLabel(
                value=intent, confidence=0.6, evidence="Reports a finding"
            ),
            "claim_type": ProposedFrameLabel(value="result", confidence=0.8),
            "register": ProposedFrameLabel(value="formal", confidence=0.8),
            "general_function": ProposedFrameLabel(value="none_of_these", confidence=0.8),
            "section_scope": ProposedFrameLabel(value="RESULTS", confidence=0.8),
        },
    )


def test_two_pass_agreement_keeps_lower_confidence_and_anchor_conflicts() -> None:
    candidate_id = uuid4()
    merged = merge_frame_labels(
        candidate_id=candidate_id,
        pass_a=_output(candidate_id),
        pass_b=_output(candidate_id),
        anchors={"intent": "compare_performance"},
        vocabulary=load_policy_bundle().frame_label_vocabulary,
    )
    by_code = {label.label_code: label for label in merged}
    assert by_code["intent"].value == "report_finding"
    assert by_code["intent"].confidence == 0.6
    assert by_code["intent"].agreement == "both_agree"
    assert by_code["intent"].source == "ai:2pass"
    assert by_code["intent"].evidence == [
        {"pass": "a", "text": "Reports a finding"},
        {"pass": "b", "text": "Reports a finding"},
    ]
    assert by_code["intent"].needs_attention is True
    assert by_code["intent"].options[-1] == {
        "source": "anchor",
        "value": "compare_performance",
    }


def test_disagreement_and_only_one_confident_keep_both_options() -> None:
    candidate_id = uuid4()
    pass_a = _output(candidate_id, intent="report_finding")
    merged = merge_frame_labels(
        candidate_id=candidate_id,
        pass_a=pass_a,
        pass_b=_output(candidate_id, intent="quantify_outcome"),
        anchors={},
        vocabulary=load_policy_bundle().frame_label_vocabulary,
    )
    intent = next(label for label in merged if label.label_code == "intent")
    assert intent.value is None
    assert intent.needs_attention is True
    assert intent.agreement == "disagree"
    assert {option["value"] for option in intent.options} == {"report_finding", "quantify_outcome"}

    uncertain_b = _output(candidate_id)
    uncertain_b.labels["intent"] = ProposedFrameLabel(value="unclear", confidence=0.2)
    uncertain = merge_frame_labels(
        candidate_id=candidate_id,
        pass_a=pass_a,
        pass_b=uncertain_b,
        anchors={},
        vocabulary=load_policy_bundle().frame_label_vocabulary,
    )
    intent = next(label for label in uncertain if label.label_code == "intent")
    assert intent.agreement == "only_one_confident"


def test_hierarchy_mismatch_and_invalid_or_missing_values_are_flagged() -> None:
    candidate_id = uuid4()
    invalid = _output(candidate_id, move="explain_approach", intent="not_a_code")
    del invalid.labels["step"]
    merged = merge_frame_labels(
        candidate_id=candidate_id,
        pass_a=invalid,
        pass_b=invalid,
        anchors={},
        vocabulary=load_policy_bundle().frame_label_vocabulary,
    )
    by_code = {label.label_code: label for label in merged}
    assert by_code["intent"].value == "unclear"
    assert by_code["step"].value == "unclear"
    assert by_code["function_group"].needs_attention is True
    assert by_code["move"].needs_attention is True
