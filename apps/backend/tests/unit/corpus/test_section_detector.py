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


def test_rhetorical_heading_codes_exist_in_the_seed_taxonomy() -> None:
    seed = Path(__file__).resolve().parents[5] / "data/seed/taxonomy.json"
    payload = json.loads(seed.read_text(encoding="utf-8"))
    seeded = {section["code"] for section in payload["sections"]}

    assert set(load_policy_bundle().section_headings.sections) <= seeded
