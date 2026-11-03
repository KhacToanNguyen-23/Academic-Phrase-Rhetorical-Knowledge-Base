"""Read-time compatibility for invented mined-style frames."""

from aprkb.modules.composition.renderer import render_frame
from aprkb.modules.patterns.read_model import normalized_frame


def test_mined_bracket_frame_renders_only_when_slot_names_match():
    slots: dict[str, object] = {"X": {"type": "topic"}, "Y": {"type": "claim"}}
    frame = "[X] demonstrate that [Y]"
    normalized = normalized_frame(frame, slots)
    assert normalized == "{X} demonstrate that {Y}"
    assert render_frame(
        normalized, slots, {"X": "The invented results", "Y": "the method works"}
    ) == (
        "The invented results demonstrate that the method works",
        [],
    )
    assert normalized_frame(frame, {"X": {"type": "topic"}}) == frame
