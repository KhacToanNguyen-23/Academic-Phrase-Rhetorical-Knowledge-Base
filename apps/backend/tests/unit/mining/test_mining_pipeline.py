"""Unit tests for the mining domain."""

from uuid import uuid4

import pytest

from aprkb.modules.mining.candidate_writer import CandidateDraft, CandidateWriter
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.policies.schemas import EpistemicMarkersPolicy, MiningFilterPolicy


def test_mining_registry_has_deterministic_order_and_requirement_tags(policy_bundle):
    stages = build_stages(policy=policy_bundle.mining_filter)

    assert [stage.name for stage in stages] == [
        "sentence_filter",
        "move_classifier",
        "epistemic_tagger",
        "slot_abstractor",
        "frame_normalizer",
        "clusterer",
        "dedup_matcher",
    ]
    for stage in stages[1:]:
        assert stage.requirement_id


def test_sentence_filter_removes_inline_citations_but_keeps_remaining_sentence():
    stage = SentenceFilter(min_words=1, max_words=100)
    item = MiningItem(
        text="The result was stable [12] (Nguyen, 2020).",
        source_sentence_ids=[uuid4()],
    )

    results = stage.process([item])

    assert len(results) == 1
    assert "[12]" not in results[0].text
    assert "(Nguyen, 2020)" not in results[0].text
    assert "The result was stable" in results[0].text


def test_sentence_filter_applies_configured_word_bounds():
    stage = SentenceFilter(min_words=2, max_words=4)
    items = [
        MiningItem(text="Short.", source_sentence_ids=[uuid4()]),
        MiningItem(text="One two three four five.", source_sentence_ids=[uuid4()]),
        MiningItem(text="One two three.", source_sentence_ids=[uuid4()]),
    ]

    results = stage.process(items)

    assert [item.text for item in results] == ["One two three."]


def test_mining_filter_thresholds_come_from_validated_policy():
    policy = MiningFilterPolicy.model_validate(
        {
            "version": "0.1.0",
            "sentence_filter": {"min_words": 1, "max_words": 10},
            "noise_filter": {
                "excluded_sections": [],
                "min_table_pipes": 2,
                "max_math_symbol_ratio": 0.5,
                "max_numeric_token_ratio": 0.5,
            },
        }
    )
    stage = build_stages(policy=policy)[0]

    assert stage.process([MiningItem(text="Short sentence.", source_sentence_ids=[uuid4()])])


def test_invalid_filter_bounds_and_blank_lexicon_entries_are_rejected():
    with pytest.raises(ValueError, match="min_words"):
        MiningFilterPolicy.model_validate(
            {
                "version": "0.1.0",
                "sentence_filter": {"min_words": 11, "max_words": 10},
                "noise_filter": {
                    "excluded_sections": [],
                    "min_table_pipes": 2,
                    "max_math_symbol_ratio": 0.5,
                    "max_numeric_token_ratio": 0.5,
                },
            }
        )
    with pytest.raises(ValueError, match="markers"):
        EpistemicMarkersPolicy.model_validate(
            {
                "version": "0.1.0",
                "markers": {
                    "low": [" "],
                    "moderate": ["suggest"],
                    "high": ["show"],
                    "absolute": ["prove"],
                },
            }
        )


def test_candidate_writer_rejects_missing_source_sentence_ids():
    writer = CandidateWriter(repository=None)
    draft = CandidateDraft(canonical_frame="The results {verb}.", source_sentence_ids=[])

    with pytest.raises(ValueError, match="source_sentence_ids"):
        writer.write(draft)
