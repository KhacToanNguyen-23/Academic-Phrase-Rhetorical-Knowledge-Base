import pytest
from pydantic import ValidationError

from aprkb.modules.gold.labels import GoldLabels


def test_gold_labels_accept_valid_offsets_and_enum_values():
    labels = GoldLabels.model_validate(
        {
            "keep": True,
            "section": "RESULTS",
            "epistemic_strength": "moderate",
            "tense": "present",
            "frame": "These results suggest that [X].",
            "slots": [{"name": "X", "char_start": 40, "char_end": 57}],
            "ownership": "own",
        }
    )
    assert labels.keep


def test_gold_labels_reject_slot_ranges_without_source_text_context():
    with pytest.raises(ValidationError):
        GoldLabels.model_validate(
            {
                "keep": True,
                "section": "RESULTS",
                "epistemic_strength": "moderate",
                "tense": "present",
                "frame": "[X]",
                "slots": [{"name": "X", "char_start": 5, "char_end": 4}],
                "ownership": "unclear",
            }
        )


def test_noise_reason_is_required_only_for_discarded_items():
    with pytest.raises(ValidationError):
        GoldLabels.model_validate({"keep": False})


def test_gold_labels_reject_slot_ranges_outside_sentence():
    labels = GoldLabels.model_validate(
        {
            "keep": True,
            "frame": "[X]",
            "slots": [{"name": "X", "char_start": 1, "char_end": 7}],
        }
    )
    with pytest.raises(ValueError, match="outside"):
        labels.validate_source_offsets("short")


_FRAME_SENTENCE = "These results suggest that seedlings tolerate cold."


def _frame_labels(frame: str, start: int = 27, end: int = 50) -> GoldLabels:
    return GoldLabels.model_validate(
        {
            "keep": True,
            "frame": frame,
            "slots": [{"name": "X", "char_start": start, "char_end": end}],
        }
    )


def test_frame_matching_source_with_slots_is_accepted():
    _frame_labels("These results suggest that [X].").validate_frame_matches_source(_FRAME_SENTENCE)


def test_frame_that_drops_leading_text_is_rejected():
    with pytest.raises(ValueError, match="frame does not match"):
        _frame_labels("suggest that [X].").validate_frame_matches_source(_FRAME_SENTENCE)


def test_frame_check_ignores_rejected_items():
    labels = GoldLabels.model_validate({"keep": False, "noise_reason": "fragment"})
    assert labels.validate_frame_matches_source("anything") is labels


def test_kept_label_requires_a_frame():
    labels = GoldLabels.model_validate({"keep": True, "frame": None, "slots": []})
    with pytest.raises(ValueError, match="requires a frame"):
        labels.validate_frame_matches_source("A self-authored sentence.")
