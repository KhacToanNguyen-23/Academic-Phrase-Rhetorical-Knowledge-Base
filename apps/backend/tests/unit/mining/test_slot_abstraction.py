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

    assert result.slots["X"].type == "noun_phrase"
    assert result.slots["Y"].type == "clause"
    assert result.ownership == "unclear"


def test_ownership_rules_for_subject_types_and_contextual_cues():
    cases = [
        ("We show that the baseline improves across repeated runs.", None, "own"),
        ("Our study shows that the baseline improves across repeated runs.", None, "own"),
        ("The present study shows that the baseline improves across repeated runs.", None, "own"),
        ("Their results show that the baseline improves across repeated runs.", None, "prior"),
        ("Prior studies show that the baseline improves across repeated runs.", None, "prior"),
        ("Earlier studies show that the baseline improves across repeated runs.", None, "prior"),
        ("These results suggest that the baseline improves across repeated runs.", None, "own"),
        (
            "These results suggest that the baseline improves across repeated runs.",
            "We propose a new method.",
            "own",
        ),
        (
            "These results suggest that the baseline improves across repeated runs.",
            "We propose a new method [12].",
            "unclear",
        ),
        ("Lee et al. [12] showed that the baseline improves across repeated runs.", None, "prior"),
    ]
    for text, previous_text, expected in cases:
        [result] = _pipeline().process(
            [MiningItem(text=text, source_sentence_ids=[uuid4()], previous_text=previous_text)]
        )
        assert result.ownership == expected


def test_tier_b_determiner_is_a_slot_when_no_blocker_applies():
    item = MiningItem(
        text="These results suggest that the baseline improves across repeated runs.",
        source_sentence_ids=[uuid4()],
        section_code="RESULTS",
    )
    [result] = _pipeline().process([item])

    assert result.slots["X"].type == "determiner_own"
    assert result.ownership == "own"


def test_versioned_ownership_policy_contains_the_reviewed_tier_lists(policy_bundle):
    policy = policy_bundle.slot_abstraction

    assert policy.version == "0.4.0"
    assert policy.own_determiners == ["our", "the present", "the current"]
    assert policy.own_head_nouns == ["paper", "study", "article"]
    assert set(policy.contextual_own_pairs) == {
        "these results",
        "these findings",
        "this result",
        "this finding",
        "this method",
        "this approach",
        "this model",
        "this work",
    }
    assert policy.prior_determiners == ["their", "prior", "previous", "earlier"]
    assert set(policy.prior_head_pairs) == {"these studies", "these authors"}


def test_ownership_tiers_use_determiner_and_head_noun():
    cases = [
        ("Our model", None, "RESULTS", "own", "determiner_own"),
        ("The present model", None, "RESULTS", "own", "determiner_own"),
        ("The current model", None, "RESULTS", "own", "determiner_own"),
        ("This paper", None, "RESULTS", "own", "determiner_own"),
        ("This study", None, "RESULTS", "own", "determiner_own"),
        ("This article", None, "RESULTS", "own", "determiner_own"),
        ("These results", None, "RESULTS", "own", "determiner_own"),
        ("These findings", None, "RESULTS", "own", "determiner_own"),
        ("This result", None, "RESULTS", "own", "determiner_own"),
        ("This finding", None, "RESULTS", "own", "determiner_own"),
        ("This method", None, "RESULTS", "own", "determiner_own"),
        ("This approach", None, "RESULTS", "own", "determiner_own"),
        ("This model", None, "RESULTS", "own", "determiner_own"),
        ("This work", None, "RESULTS", "own", "determiner_own"),
        ("These methods", None, "RESULTS", "unclear", "noun_phrase"),
        ("This phenomenon", None, "RESULTS", "unclear", "noun_phrase"),
        ("These studies", None, "RESULTS", "prior", "determiner_prior"),
        ("These authors", None, "RESULTS", "prior", "determiner_prior"),
        ("These results", "The evaluation supports this work.", "RESULTS", "own", "determiner_own"),
        (
            "These results",
            "Earlier studies report similar trends.",
            "RESULTS",
            "unclear",
            "noun_phrase",
        ),
        ("These results", None, "INTRO", "unclear", "noun_phrase"),
        ("These results", None, "RELATED_WORK", "unclear", "noun_phrase"),
        ("These results", "A result was observed [12].", "RESULTS", "unclear", "noun_phrase"),
        ("These results", None, None, "own", "determiner_own"),
        ("These results", None, "RESULTS", "own", "determiner_own"),
    ]
    for subject, previous_text, section_code, expected, slot_type in cases:
        [result] = _pipeline().process(
            [
                MiningItem(
                    text=f"{subject} suggest that the sample changes.",
                    source_sentence_ids=[uuid4()],
                    previous_text=previous_text,
                    section_code=section_code,
                )
            ]
        )
        assert result.ownership == expected
        assert result.slots["X"].type == slot_type


def test_citation_precedence_and_we_ownership_are_unchanged():
    cases = [
        ("Our study [12]", "prior", "determiner_prior"),
        ("We [12]", "prior", "noun_phrase"),
        ("We", "own", "noun_phrase"),
    ]
    for subject, expected, slot_type in cases:
        [result] = _pipeline().process(
            [
                MiningItem(
                    text=f"{subject} show that the sample changes.", source_sentence_ids=[uuid4()]
                )
            ]
        )
        assert result.ownership == expected
        assert result.slots["X"].type == slot_type


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


def test_slot_text_does_not_split_a_cluster():
    sentences = [
        "Our results suggest that the mock system improves retrieval quality.",
        "Our results suggest that the mock system reduces retrieval errors.",
        "Our results suggest that the mock system improves retrieval quality [12].",
    ]
    results = [
        _pipeline().process([MiningItem(text=text, source_sentence_ids=[uuid4()])])[0]
        for text in sentences
    ]

    assert len({result.cluster_key for result in results}) == 1


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


def _frame(text: str) -> str | None:
    results = _pipeline().process([MiningItem(text=text, source_sentence_ids=[uuid4()])])
    return results[0].text if results else None


def test_negation_and_modals_stay_literal_in_the_frame():
    assert (
        _frame("These findings do not suggest that the sample changes.")
        == "[X] [Y] do not suggest that [Z]."
    )
    assert (
        _frame("Our results may suggest that the sample changes.")
        == "[X] [Y] may suggest that [Z]."
    )
    assert _frame("Smith et al. never show that cold slows growth.") == "[X] never show that [Y]."


def test_negated_and_plain_sentences_do_not_share_a_cluster_key():
    keys = {
        _pipeline().process([MiningItem(text=text, source_sentence_ids=[uuid4()])])[0].cluster_key
        for text in (
            "Our results suggest that the sample changes.",
            "Our results do not suggest that the sample changes.",
        )
    }
    assert len(keys) == 2


def test_did_not_is_past_tense():
    [result] = _pipeline().process(
        [
            MiningItem(
                text="Our results did not show that the sample changes.",
                source_sentence_ids=[uuid4()],
            )
        ]
    )
    assert result.tense == "past"
    assert result.text == "[X] [Y] did not show that [Z]."


def test_regex_path_records_modality_without_changing_its_frame():
    sentences = [
        "Our results could indicate that the baseline improves across repeated runs.",
        "The results might have suggested that the baseline improves across repeated runs.",
        "The method may address concerns and show that the baseline improves across repeated runs.",
    ]
    results = [
        _pipeline().process([MiningItem(text=text, source_sentence_ids=[uuid4()])])[0]
        for text in sentences
    ]

    assert [result.modality for result in results] == ["could", "might", None]
    assert results[0].text == "[X] [Y] could indicate that [Z]."
    assert results[1].text == "[X] might have suggested that [Y]."
    assert results[2].modality is None
