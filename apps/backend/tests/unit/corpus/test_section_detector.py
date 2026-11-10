"""Heading to section code mapping (phase 01)."""

import json
from pathlib import Path

from aprkb.modules.corpus.parsers.base import ParsedSection
from aprkb.modules.corpus.section_detector import SectionDetector
from aprkb.policies.loader import load_policy_bundle


def _detect(*headings: str | None) -> list[str | None]:
    detector = SectionDetector(load_policy_bundle().section_headings)
    sections = [
        ParsedSection(heading=heading, text="", order=index, char_start=0)
        for index, heading in enumerate(headings)
    ]
    return detector.detect(sections)


def test_numbered_headings_map_and_sub_headings_inherit() -> None:
    assert _detect(
        "A Study Title",
        "Abstract",
        "Full Text",
        "1. Introduction",
        "2. Literature review",
        "2.1. Earlier systems",
        "3. Materials and Methods",
        "3.2 Experimental setup",
        "Page header 12 (2027)",
        "4. Results",
        "5 DISCUSSION",
        "6. Conclusions",
        "References",
    ) == [
        None,
        "ABSTRACT",
        None,
        "INTRO",
        "RELATED_WORK",
        "RELATED_WORK",
        "METHODS",
        "METHODS",
        "METHODS",
        "RESULTS",
        "DISCUSSION",
        "CONCLUSION",
        "REFERENCES",
    ]


def test_roman_numerals_and_unknown_top_headings() -> None:
    assert _detect("I. Introduction", "II. A Custom Algorithm", "II.1 Details") == [
        "INTRO",
        None,
        None,
    ]


def test_out_of_sequence_numbers_and_paragraph_titles_inherit() -> None:
    assert _detect("1. Introduction", "2. Methods", "14 return labels", "Methods", "3 Results") == [
        "INTRO",
        "METHODS",
        "METHODS",
        "METHODS",
        "RESULTS",
    ]


def test_back_matter_and_appendix_are_non_rhetorical() -> None:
    assert _detect(
        "1 Introduction",
        "2 Concluding remarks",
        "A PRELIMINARY MATERIAL",
        "B.1 Notation",
        "Acknowledgements",
        "Declaration of competing interest",
        "Figures and Tables",
    ) == [
        "INTRO",
        "CONCLUSION",
        "APPENDIX",
        "APPENDIX",
        "BACK_MATTER",
        "BACK_MATTER",
        "FIGURES_TABLES",
    ]


def test_unnumbered_documents_match_every_heading() -> None:
    assert _detect(None, "Introduction", "Background", "Discussion") == [
        None,
        "INTRO",
        "RELATED_WORK",
        "DISCUSSION",
    ]


def test_missing_parent_opens_implicit_top_section_without_inheriting_previous_code() -> None:
    sections = [
        ParsedSection(heading=heading, text="", order=index, char_start=0)
        for index, heading in enumerate(("1. Introduction", "2.1. Methods", "2.2. Details"))
    ]
    labels = SectionDetector(load_policy_bundle().section_headings).detect_with_provenance(sections)

    assert [(row.code, row.secondary_code, row.source) for row in labels] == [
        ("INTRO", None, "heading"),
        ("METHODS", None, "implicit_parent"),
        ("METHODS", None, "inherited"),
    ]


def test_unmatched_implicit_parent_does_not_inherit_previous_top_code() -> None:
    assert _detect("1. Introduction", "2.1. Custom topic", "2.2. Details") == [
        "INTRO",
        None,
        None,
    ]
    sections = [
        ParsedSection(heading=heading, text="", order=index, char_start=0)
        for index, heading in enumerate(("1. Introduction", "2.1. Custom topic"))
    ]
    label = SectionDetector(load_policy_bundle().section_headings).detect_with_provenance(sections)[
        1
    ]
    assert (label.code, label.source) == (None, "implicit_parent")
    labels = SectionDetector(load_policy_bundle().section_headings).detect_with_provenance(
        sections + [ParsedSection(heading="2.2. Further details", text="", order=2, char_start=0)]
    )
    assert (labels[2].code, labels[2].source) == (None, "inherited")


def test_bare_numbered_heading_opens_a_new_section() -> None:
    assert _detect("1. Introduction", "2.", "3. Results") == ["INTRO", None, "RESULTS"]


def test_algorithm_and_numbered_list_lines_are_not_top_headings() -> None:
    assert _detect(
        "1. Introduction", "2. Methods", "14 return labels", "15. Return the result.", "3. Results"
    ) == ["INTRO", "METHODS", "METHODS", "METHODS", "RESULTS"]


def test_too_large_gap_and_decreasing_top_numbers_are_rejected() -> None:
    assert _detect(
        "1. Introduction", "2. Methods", "6. Results", "1. Conclusion", "3. Results"
    ) == ["INTRO", "METHODS", "METHODS", "METHODS", "RESULTS"]


def test_compound_heading_keeps_both_codes_and_primary_code() -> None:
    sections = [
        ParsedSection(heading=heading, text="", order=index, char_start=0)
        for index, heading in enumerate(("1. Introduction", "2. Results and Discussion"))
    ]
    label = SectionDetector(load_policy_bundle().section_headings).detect_with_provenance(sections)[
        1
    ]

    assert (label.code, label.secondary_code, label.source) == ("RESULTS", "DISCUSSION", "heading")


def test_full_text_reset_and_provenance_sources() -> None:
    sections = [
        ParsedSection(heading=heading, text="", order=index, char_start=0)
        for index, heading in enumerate(
            ("Introduction", "Context", "Full Text", "Introduction", "Discussion")
        )
    ]
    labels = SectionDetector(load_policy_bundle().section_headings).detect_with_provenance(sections)

    assert [(row.code, row.source) for row in labels] == [
        ("INTRO", "heading"),
        ("INTRO", "inherited"),
        (None, "none"),
        ("INTRO", "heading"),
        ("DISCUSSION", "heading"),
    ]


def test_rhetorical_heading_codes_exist_in_the_seed_taxonomy() -> None:
    seed = Path(__file__).resolve().parents[5] / "data/seed/taxonomy.json"
    payload = json.loads(seed.read_text(encoding="utf-8"))
    seeded = {section["code"] for section in payload["sections"]}

    assert set(load_policy_bundle().section_headings.sections) <= seeded


def _labels(*headings: str | None):
    sections = [
        ParsedSection(heading=heading, text="", order=index, char_start=0)
        for index, heading in enumerate(headings)
    ]
    return sections


def test_formal_environment_headings_are_excluded_as_appendix() -> None:
    sections = _labels(
        "1 Introduction",
        "2 Methods",
        "Theorem 2.",
        "Lemma 3.",
        "Proof.",
        "Remark 2.",
        "Corollary 1",
        "Proposition 2",
        "Assumption 3",
        "Claim 1",
        "4 Results",
    )
    assert SectionDetector(load_policy_bundle().section_headings).detect(sections) == [
        "INTRO",
        "METHODS",
        "APPENDIX",
        "APPENDIX",
        "APPENDIX",
        "APPENDIX",
        "APPENDIX",
        "APPENDIX",
        "APPENDIX",
        "APPENDIX",
        "RESULTS",
    ]


def test_lettered_appendix_subsections_are_excluded_with_or_without_appendix_heading() -> None:
    detector = SectionDetector(load_policy_bundle().section_headings)
    assert detector.detect(
        _labels("1 Introduction", "Appendix", "C.1 Convergence", "C.2.3 Details")
    ) == ["INTRO", "APPENDIX", "APPENDIX", "APPENDIX"]
    assert detector.detect(_labels("1 Introduction", "C.1 Convergence", "C.2.3 Details")) == [
        "INTRO",
        "APPENDIX",
        "APPENDIX",
    ]


def test_definition_and_assumption_policy_excludes_or_inherits_in_methods() -> None:
    base = load_policy_bundle().section_headings
    sections = _labels("1 Introduction", "2 Methods", "Definition 1", "Assumption 2", "3 Results")
    exclude = SectionDetector(base.model_copy(update={"formal_block_policy": "exclude"}))
    inherit = SectionDetector(base.model_copy(update={"formal_block_policy": "inherit"}))
    assert exclude.detect(sections) == ["INTRO", "METHODS", "APPENDIX", "APPENDIX", "RESULTS"]
    assert inherit.detect(sections) == ["INTRO", "METHODS", "METHODS", "METHODS", "RESULTS"]


def test_inference_is_reporting_only_and_subheadings_inherit_provenance() -> None:
    sections = _labels("1 Introduction", "2 Custom Topic", "2.1 Details", "3 Results")
    detector = SectionDetector(load_policy_bundle().section_headings)
    assert detector.detect(sections) == ["INTRO", None, None, "RESULTS"]
    assert detector.detect(sections, infer_methods=True) == [
        "INTRO",
        "METHODS",
        "METHODS",
        "RESULTS",
    ]
    labels = detector.detect_with_provenance(sections)
    assert [(item.code, item.inferred_code, item.source) for item in labels] == [
        ("INTRO", None, "heading"),
        (None, "METHODS", "inferred"),
        (None, "METHODS", "inferred"),
        ("RESULTS", None, "heading"),
    ]


def test_inference_requires_both_anchor_sides_and_does_not_cross_formal_blocks() -> None:
    detector = SectionDetector(load_policy_bundle().section_headings)
    assert detector.detect(_labels("1 Introduction", "2 Custom Topic"), infer_methods=True) == [
        "INTRO",
        None,
    ]
    assert detector.detect(
        _labels("1 Introduction", "2 Custom Topic", "Theorem 2", "3 Results"),
        infer_methods=True,
    ) == ["INTRO", None, "APPENDIX", "RESULTS"]
    assert detector.detect(
        _labels("1 Introduction", "2 Custom Topic", "C.1 Appendix detail", "3 Results"),
        infer_methods=True,
    ) == ["INTRO", None, "APPENDIX", "RESULTS"]


def test_inferred_methods_code_does_not_change_mining_filter_or_ownership_input() -> None:
    from aprkb.modules.mining.stages.base import MiningItem
    from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
    from aprkb.modules.mining.stages.slot_abstractor import infer_ownership
    from aprkb.policies.loader import load_policy_bundle

    sections = _labels("1 Introduction", "2 Custom Topic", "3 Results")
    detector = SectionDetector(load_policy_bundle().section_headings)
    label = detector.detect_with_provenance(sections)[1]
    noise = load_policy_bundle().mining_filter.noise_filter
    item = MiningItem(
        text="We show that this method improves the result.",
        source_sentence_ids=[],
        section_code=label.code,
    )
    assert label.inferred_code == "METHODS"
    assert label.code is None
    # The production ingest API consumes detect(), so the filter receives the heading code only.
    assert SectionDetector(load_policy_bundle().section_headings).detect(sections)[1] is None
    sentence_filter = SentenceFilter(min_words=5, max_words=60, noise=noise)
    assert sentence_filter.reject_reason(item) is None
    excluded = MiningItem(text=item.text, source_sentence_ids=[], section_code="APPENDIX")
    assert sentence_filter.reject_reason(excluded) == "excluded_section"
    policy = load_policy_bundle().slot_abstraction
    assert infer_ownership("this method", None, policy, label.code) == infer_ownership(
        "this method", None, policy, None
    )


def test_added_heading_keywords_are_prefix_matched_and_non_rhetorical() -> None:
    labels = SectionDetector(load_policy_bundle().section_headings).detect(
        _labels(
            "1 Numerical results and ablation",
            "2 Summary and outlook",
            "3 Artifact appendix",
            "4 Reproducibility statement",
            "5 Checklist",
            "6 We report numerical results",
        )
    )
    assert labels == ["RESULTS", "CONCLUSION", "APPENDIX", "BACK_MATTER", "APPENDIX", "APPENDIX"]


def test_unknown_parent_subheading_can_match_its_own_rhetorical_heading() -> None:
    sections = _labels("1 Custom", "1.2 Related Work", "1.2.1 Earlier systems")
    labels = SectionDetector(load_policy_bundle().section_headings).detect_with_provenance(sections)

    assert [(item.code, item.source) for item in labels] == [
        (None, "none"),
        ("RELATED_WORK", "heading"),
        ("RELATED_WORK", "inherited"),
    ]


def test_subheading_own_match_does_not_leak_to_later_siblings() -> None:
    sections = _labels(
        "1 Introduction",
        "2 Related Work",
        "4 Our Study",
        "4.1 Overview",
        "4.2 Evaluation Metrics",
        "4.3 Experiments on Tabular Dataset",
        "4.4 Experiments on Text Dataset",
        "4.5 Experiments on Image Dataset",
        "4.6 Quantitative Comparison of Training Cost",
        "5 Conclusion",
    )

    labels = SectionDetector(load_policy_bundle().section_headings).detect_with_provenance(sections)

    assert [(item.code, item.source) for item in labels[4:8]] == [
        ("METHODS", "heading"),
        ("RESULTS", "heading"),
        ("RESULTS", "heading"),
        ("RESULTS", "heading"),
    ]
    assert labels[8].code is None


def test_subheading_own_match_is_inherited_only_by_its_deeper_descendants() -> None:
    sections = _labels(
        "1 Introduction",
        "2 Related Work",
        "4 Our Study",
        "4.2 Evaluation Metrics",
        "4.2.1 Metric Definitions",
        "4.2.1.1 Accuracy Metric",
        "4.3 Overview",
    )

    labels = SectionDetector(load_policy_bundle().section_headings).detect_with_provenance(sections)

    assert [(item.code, item.source) for item in labels[3:]] == [
        ("METHODS", "heading"),
        ("METHODS", "inherited"),
        ("METHODS", "inherited"),
        (None, "inherited"),
    ]


def test_sibling_without_own_match_returns_to_unknown_top_label() -> None:
    labels = SectionDetector(load_policy_bundle().section_headings).detect_with_provenance(
        _labels(
            "1 Introduction",
            "2 Related Work",
            "4 Our Study",
            "4.2 Evaluation Metrics",
            "Unlabeled note",
            "4.3 Overview",
        )
    )

    assert [(item.code, item.source) for item in labels[3:]] == [
        ("METHODS", "heading"),
        (None, "none"),
        (None, "inherited"),
    ]


def test_long_methods_subheadings_override_labeled_top_section() -> None:
    labels = SectionDetector(load_policy_bundle().section_headings).detect_with_provenance(
        _labels(
            "1 Introduction",
            "1.1 Evaluation Metrics",
            "1.2 Experiments on Text Dataset",
            "1.3 Overview",
        )
    )

    assert [(item.code, item.source) for item in labels] == [
        ("INTRO", "heading"),
        ("METHODS", "heading"),
        ("INTRO", "inherited"),
        ("INTRO", "inherited"),
    ]


def test_long_methods_descendant_overrides_its_labeled_parent() -> None:
    assert _detect("1 Introduction", "1.1 Results", "1.1.1 Evaluation Metrics") == [
        "INTRO",
        "INTRO",
        "METHODS",
    ]


def test_appendix_region_keeps_non_rhetorical_code_through_implicit_numbers() -> None:
    assert _detect(
        "1 Introduction",
        "2 Appendix",
        "A.1 Supplementary Data",
        "1) Dataset details",
        "5.1.1 Dataset Details",
        "5.1.2 Additional Results",
        "6 Conclusion",
    ) == [
        "INTRO",
        "APPENDIX",
        "APPENDIX",
        "APPENDIX",
        "APPENDIX",
        "APPENDIX",
        "CONCLUSION",
    ]


def test_back_matter_region_keeps_exclusion_through_implicit_numbers() -> None:
    assert _detect(
        "1 Introduction", "Back Matter", "5.1.1 Author Contributions", "6 Conclusion"
    ) == ["INTRO", "BACK_MATTER", "BACK_MATTER", "CONCLUSION"]


def test_references_and_figures_regions_remain_excluded_through_numbered_children() -> None:
    assert _detect("1 Introduction", "2 References", "5.1.1 Citation entries", "6 Conclusion") == [
        "INTRO",
        "REFERENCES",
        "REFERENCES",
        "CONCLUSION",
    ]
    assert _detect(
        "1 Introduction", "Figures and Tables", "5.1.1 Table listings", "6 Conclusion"
    ) == ["INTRO", "FIGURES_TABLES", "FIGURES_TABLES", "CONCLUSION"]


def test_formal_block_does_not_anchor_unrelated_sibling_headings() -> None:
    assert _detect("1 Introduction", "2 Custom Topic", "Remark 1", "2.1 Discussion") == [
        "INTRO",
        None,
        "APPENDIX",
        "DISCUSSION",
    ]


def test_benchmark_evaluation_and_experiment_setup_phrases_take_methods_priority() -> None:
    assert _detect(
        "1 Benchmarking Suites",
        "2 Benchmark Module",
        "3 Experiment Tools",
        "4 Evaluation Metrics",
        "5 Evaluation",
        "6 Benchmark",
    ) == ["METHODS", "METHODS", "METHODS", "METHODS", "RESULTS", "RESULTS"]


def test_long_methods_phrase_overrides_labeled_parent_with_subtree_scope() -> None:
    labels = SectionDetector(load_policy_bundle().section_headings).detect_with_provenance(
        _labels(
            "1 Results",
            "1.1 Evaluation Metrics",
            "1.1.1 Evaluation environment",
            "1.2 Overview",
            "1.3 Evaluation metrics",
        )
    )

    assert [(item.code, item.source) for item in labels] == [
        ("RESULTS", "heading"),
        ("METHODS", "heading"),
        ("METHODS", "inherited"),
        ("RESULTS", "inherited"),
        ("METHODS", "heading"),
    ]


def test_long_methods_phrase_does_not_override_non_rhetorical_parent() -> None:
    for parent, expected in (
        ("1 Appendix", "APPENDIX"),
        ("1 References", "REFERENCES"),
        ("1 Back Matter", "BACK_MATTER"),
        ("1 Figures and Tables", "FIGURES_TABLES"),
    ):
        assert _detect(
            parent,
            "1.1 Evaluation Metrics",
            "1.1.1 Benchmarking Tools",
            "1.2 Additional Data",
        ) == [expected, expected, expected, expected]


def test_sandwich_is_opt_in_and_keeps_provenance_separate() -> None:
    sections = _labels("1 Introduction", "2 Custom topic", "2.1 Details", "3 Introduction")
    detector = SectionDetector(load_policy_bundle().section_headings)

    default = detector.detect_with_provenance(sections)
    measured = detector.detect_with_provenance(sections, apply_sandwich=True)

    assert (default[1].code, default[1].source, default[2].code) == (
        None,
        "none",
        None,
    )
    assert [(item.code, item.source) for item in measured] == [
        ("INTRO", "heading"),
        ("INTRO", "sandwich"),
        ("INTRO", "inherited"),
        ("INTRO", "heading"),
    ]


def test_sandwich_requires_same_allowed_nearest_heading_code() -> None:
    detector = SectionDetector(load_policy_bundle().section_headings)
    assert (
        detector.detect_with_provenance(
            _labels("1 Introduction", "2 Custom", "3 Methods"), apply_sandwich=True
        )[1].source
        == "none"
    )
    assert (
        detector.detect_with_provenance(
            _labels("1 Methods", "2 Custom", "3 Methods"), apply_sandwich=True
        )[1].source
        == "none"
    )
    labels = detector.detect_with_provenance(
        _labels("1 Introduction", "2 Custom", "2.1 Theorem 1", "3 Introduction"),
        apply_sandwich=True,
    )
    assert labels[1].source == "none"
    assert labels[2].code == "APPENDIX"
