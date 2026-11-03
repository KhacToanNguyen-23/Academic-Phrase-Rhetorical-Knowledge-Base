"""Composer checks: no invented content or template execution."""

import pytest

from aprkb.modules.composition.renderer import SlotValidationError, render_frame


def test_missing_slot_remains_a_placeholder_and_values_are_literal() -> None:
    text, unfilled = render_frame(
        "The role of {topic} in {context} remains underexplored.",
        {
            "topic": {"type": "noun_phrase", "required": True},
            "context": {"type": "noun_phrase", "required": False},
        },
        {"topic": "{context}"},
    )

    assert text == "The role of {context} in {context} remains underexplored."
    assert unfilled == ["context"]


def test_required_empty_and_too_short_slots_return_field_specific_errors() -> None:
    schema = {
        "topic": {"type": "noun_phrase", "required": True, "min_length": 4},
        "context": {"type": "noun_phrase", "required": True, "min_length": 3},
    }
    with pytest.raises(SlotValidationError) as exc_info:
        render_frame("{topic} in {context}.", schema, {"topic": "AI", "context": ""})

    assert exc_info.value.field_errors == {
        "topic": "Enter at least 4 characters.",
        "context": "This field is required.",
    }


def test_optional_empty_slot_remains_as_placeholder() -> None:
    text, unfilled = render_frame(
        "The role of {topic} in {context}.",
        {
            "topic": {"type": "noun_phrase", "required": True, "min_length": 1},
            "context": {"type": "noun_phrase", "required": False, "min_length": 5},
        },
        {"topic": "models", "context": "  "},
    )

    assert text == "The role of models in {context}."
    assert unfilled == ["context"]


@pytest.mark.parametrize(
    ("frame", "schema", "values"),
    [
        ("The {topic}.", {}, {}),
        ("The {topic}.", {"topic": "noun_phrase"}, {"invented": "x"}),
        ("The {topic}.", {"topic": 1}, {"topic": "x"}),
    ],
)
def test_invalid_pattern_or_slot_is_rejected(frame, schema, values) -> None:
    with pytest.raises(ValueError):
        render_frame(frame, schema, values)
