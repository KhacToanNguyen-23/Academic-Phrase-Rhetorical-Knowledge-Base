from copy import deepcopy

import pytest
from pydantic import ValidationError

from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import FrameLabelVocabularyPolicy


def test_frame_vocabulary_has_unique_codes_and_valid_hierarchy() -> None:
    policies = load_policy_bundle()
    vocabulary = policies.frame_label_vocabulary

    assert len(vocabulary.intents) == 30
    assert all(
        {"unclear", "none_of_these"} <= {entry.code for entry in getattr(vocabulary, field)}
        for field in (
            "function_groups",
            "moves",
            "steps",
            "intents",
            "claim_types",
            "registers",
            "allowed_sections",
            "general_functions",
            "source_classes",
        )
    )
    assert {
        anchor.intent_hint: vocabulary.function_group_for_intent(anchor.intent_hint)
        for anchor in policies.frame_function_anchors.anchors
    } == {
        "compare_performance": "REPORTING_RESULTS",
        "acknowledge_limitation": "DISCUSSING_FINDINGS",
        "suggest_future_work": "WRITING_CONCLUSIONS",
        "defining_classifying": "GENERAL_FUNCTIONS",
    }


def test_frame_vocabulary_rejects_duplicate_codes_and_missing_parents() -> None:
    raw = load_policy_bundle().frame_label_vocabulary.model_dump()
    duplicated = deepcopy(raw)
    duplicated["claim_types"].append(duplicated["claim_types"][0])
    with pytest.raises(ValidationError, match="codes must be unique"):
        FrameLabelVocabularyPolicy.model_validate(duplicated)

    missing_parent = deepcopy(raw)
    missing_parent["intents"][0]["parent"] = "no_such_step"
    with pytest.raises(ValidationError, match="intent parents must reference steps"):
        FrameLabelVocabularyPolicy.model_validate(missing_parent)


def test_frame_vocabulary_rejects_hierarchy_cycles() -> None:
    raw = load_policy_bundle().frame_label_vocabulary.model_dump()
    raw["moves"][0]["code"] = "INTRODUCING_WORK"
    raw["steps"][0]["parent"] = "INTRODUCING_WORK"

    with pytest.raises(ValidationError, match="contains a cycle"):
        FrameLabelVocabularyPolicy.model_validate(raw)
