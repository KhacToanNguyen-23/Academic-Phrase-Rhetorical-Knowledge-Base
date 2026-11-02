"""Contract and rule-based slot abstraction tests using authored sentences."""

from uuid import uuid4

from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.slot_abstractor import SlotAbstractor
from aprkb.policies.loader import load_policy_bundle


def _pipeline():
    return MiningPipeline(stages=build_stages(policy_bundle=load_policy_bundle()))


def test_abstraction_masks_source_arguments_and_keeps_typed_slots_and_offsets():
    source = "Our results suggest that the pilot filter improves retrieval quality [12]."
    item = MiningItem(
        text=source,
        source_sentence_ids=[uuid4()],
        section_code="RESULTS",
        char_start=120,
    )

    [result] = _pipeline().process([item])

    assert result.text == "[X] [Y] suggest that [Z]."
    assert result.slots["X"].type == "determiner_own"
    assert result.slots["Y"].type == "noun_phrase"
    assert result.slots["Z"].type == "clause"
    assert result.confidence is None
    assert "pilot filter" not in result.text
    assert "retrieval quality" not in str(result.slots)
    assert len(result.occurrences) == 1
    occurrence = result.occurrences[0]
    assert occurrence.sentence_id == item.source_sentence_ids[0]
    assert source[
        occurrence.slot_spans["Z"][0] - item.char_start : occurrence.slot_spans["Z"][1]
        - item.char_start
    ]
    assert (
        "[12]"
        in source[
            occurrence.slot_spans["Z"][0] - item.char_start : occurrence.slot_spans["Z"][1]
            - item.char_start
        ]
    )


def test_tense_strength_and_ownership_are_separate_cluster_keys():
    sentences = [
        "Our results suggest that the sample changes.",
        "Our results suggested that the sample changes.",
        "Our results prove that the sample changes.",
        "Previous studies suggest that the sample changes.",
    ]
    results = []
    for text in sentences:
        results.extend(
            _pipeline().process(
                [MiningItem(text=text, source_sentence_ids=[uuid4()], section_code="RESULTS")]
            )
        )

    assert len(results) == 4
    assert results[0].tense == "present"
    assert results[1].tense == "past"
    assert results[2].epistemic_strength == "absolute"
    assert results[3].ownership == "prior"
    assert len({result.cluster_key for result in results}) == 4


def test_previous_prior_context_blocks_ownership_inference():
    item = MiningItem(
        text="These results suggest that the sample changes.",
        source_sentence_ids=[uuid4()],
        section_code="RESULTS",
        previous_text="Earlier studies reported similar findings [3].",
    )

    [result] = _pipeline().process([item])

    assert result.ownership == "unclear"


def test_numeric_citation_in_previous_sentence_blocks_ownership_inference():
    item = MiningItem(
        text="These results suggest that the sample changes.",
        source_sentence_ids=[uuid4()],
        section_code="RESULTS",
        previous_text="The method was tested [3].",
    )

    [result] = _pipeline().process([item])

    assert result.ownership == "unclear"


def test_multiword_own_determiner_is_kept_as_a_single_typed_slot():
    item = MiningItem(
        text="The only result suggests that the sample changes.",
        source_sentence_ids=[uuid4()],
        section_code="RESULTS",
    )

    [result] = _pipeline().process([item])

    assert result.slots["X"].type == "determiner_own"
    assert result.slots["Y"].type == "noun_phrase"
    assert result.ownership == "own"


def test_reviewed_inflection_forms_share_class_key_but_keep_surface_frame():
    forms = [
        "Our results suggest that the sample changes.",
        "Our results suggests that the sample changes.",
    ]
    results = [
        _pipeline().process([MiningItem(text=text, source_sentence_ids=[uuid4()])])[0]
        for text in forms
    ]

    assert results[0].cluster_key == results[1].cluster_key
    assert results[0].text != results[1].text


def test_different_complements_and_protected_citations_do_not_share_key():
    sentences = [
        "Our results suggest that the mock system improves retrieval quality.",
        "Our results suggest that the mock system reduces retrieval errors.",
        "Our results suggest that the mock system improves retrieval quality [12].",
    ]
    results = [
        _pipeline().process([MiningItem(text=text, source_sentence_ids=[uuid4()])])[0]
        for text in sentences
    ]

    assert len({result.cluster_key for result in results}) == len(sentences)


def test_unrecognized_reporting_word_does_not_create_a_raw_candidate():
    item = MiningItem(
        text="The pilot intervention improves retrieval quality.",
        source_sentence_ids=[uuid4()],
        section_code="RESULTS",
    )

    assert _pipeline().process([item]) == []


def test_extractability_reason_reports_empty_subject_after_determiner(policy_bundle):
    from aprkb.modules.mining.stages.slot_abstractor import SlotAbstractor

    abstractor = SlotAbstractor(policy_bundle.reporting_verbs, policy_bundle.slot_abstraction)
    text = "These suggest that the sample changes."

    assert abstractor.extractability_reason(text) == "empty_noun_phrase"
    assert _pipeline().process([MiningItem(text=text, source_sentence_ids=[uuid4()])]) == []


def _abstractor():
    bundle = load_policy_bundle()
    return SlotAbstractor(bundle.reporting_verbs, bundle.slot_abstraction)


def test_extractability_reason_is_none_for_supported_construction():
    assert (
        _abstractor().extractability_reason("Our results suggest that cold slows growth.") is None
    )


def test_extractability_reason_names_the_failing_condition():
    abstractor = _abstractor()
    assert (
        abstractor.extractability_reason("This paper presents a new tool.") == "no_reporting_verb"
    )
    assert abstractor.extractability_reason("Our results suggest a new tool.") == "no_that"
    assert abstractor.extractability_reason("Results suggest that cold.") == "clause_too_short"
    assert abstractor.extractability_reason("suggest that cold slows growth.") == "no_subject"
    long_subject = "The very long and winding collection of many separate results suggest that x y."
    assert abstractor.extractability_reason(long_subject) == "subject_too_long"
