"""Composer checks: no invented content or template execution."""

import pytest

from aprkb.modules.composition.renderer import render_frame


def test_missing_slot_remains_a_placeholder_and_values_are_literal() -> None:
    text, unfilled = render_frame(
        "The role of {topic} in {context} remains underexplored.",
        {"topic": "noun_phrase", "context": "noun_phrase"},
        {"topic": "{context}"},
    )

    assert text == "The role of {context} in {context} remains underexplored."
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
