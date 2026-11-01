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
