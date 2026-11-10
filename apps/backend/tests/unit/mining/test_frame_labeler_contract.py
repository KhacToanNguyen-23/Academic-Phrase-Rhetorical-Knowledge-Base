from uuid import uuid4

import pytest
from pydantic import ValidationError

from aprkb.core.config import Settings
from aprkb.modules.mining.labelers import (
    FrameLabelerError,
    FrameLabelOutput,
    FrameLabelPayload,
    NullFrameLabeler,
    ProposedFrameLabel,
    frame_label_json_schema,
    validate_frame_label_output,
)
from aprkb.policies.loader import load_policy_bundle


@pytest.mark.asyncio
async def test_null_frame_labeler_returns_no_labels() -> None:
    result = await NullFrameLabeler().label_batch(frames=[], prompt_variant="a")
    assert result == []


def test_frame_payload_is_limited_to_masked_frame_and_metadata() -> None:
    payload = FrameLabelPayload(
        candidate_id=uuid4(),
        canonical_frame="[X] compare favorably with [Y]",
        family="Tier 1",
        epistemic_strength=None,
        paper_count=2,
        observed_section_counts={"RESULTS": 4},
        anchor_proposal={"function_group": "REPORTING_RESULTS"},
    )
    assert "text" not in payload.model_dump()
    with pytest.raises(ValidationError):
        FrameLabelPayload.model_validate({**payload.model_dump(), "source_sentence": "private"})


def test_groq_schema_uses_only_closed_vocabulary_codes() -> None:
    vocabulary = load_policy_bundle().frame_label_vocabulary
    schema = frame_label_json_schema(vocabulary)
    properties = schema["properties"]["frames"]["items"]["properties"]["labels"]["properties"]
    intent_value = properties["intent"]["properties"]["value"]
    codes = intent_value["anyOf"][0]["enum"]
    assert "compare_performance" in codes
    assert "invented_intent" not in codes


def test_pydantic_labels_reject_unknown_codes_and_long_evidence() -> None:
    vocabulary = load_policy_bundle().frame_label_vocabulary
    output = FrameLabelOutput(
        candidate_id=uuid4(),
        labels={"intent": ProposedFrameLabel(value="invented_intent", confidence=0.9)},
    )
    with pytest.raises(FrameLabelerError, match="outside the frame-label vocabulary"):
        validate_frame_label_output(output, vocabulary=vocabulary)

    with pytest.raises(ValidationError, match="no more than 15 words"):
        ProposedFrameLabel(
            value="state_objective",
            confidence=0.8,
            evidence=(
                "one two three four five six seven eight nine ten eleven twelve thirteen "
                "fourteen fifteen sixteen"
            ),
        )


def test_frame_labeler_configuration_is_local_or_test_only() -> None:
    Settings(_env_file=None, app_env="test", frame_labeler="groq")
    with pytest.raises(ValidationError, match="only allowed in local or test"):
        Settings(_env_file=None, app_env="production", frame_labeler="groq")
    with pytest.raises(ValidationError, match="must be null or groq"):
        Settings(_env_file=None, frame_labeler="other")
