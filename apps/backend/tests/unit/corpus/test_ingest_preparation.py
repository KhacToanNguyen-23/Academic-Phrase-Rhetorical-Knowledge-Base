"""Shared parser, section detector, and per-section analysis for worker and trial."""

from aprkb.modules.corpus.ingest import parse_and_analyze
from aprkb.modules.corpus.parsers import MarkdownParser
from aprkb.policies.loader import load_policy_bundle


def test_parse_and_analyze_keeps_detected_section_and_global_offsets() -> None:
    calls: list[str] = []

    def analyse(text: str) -> list[tuple[str, int, int, None, str]]:
        calls.append(text)
        return [(text, 0, len(text), None, "test:section")]

    prepared = parse_and_analyze(
        MarkdownParser(),
        b"# Abstract\n\nA short summary.\n\n# References\n\nA citation.",
        section_headings=load_policy_bundle().section_headings,
        analyse_section=analyse,
    )

    assert [section.section_code for section in prepared.sections] == ["ABSTRACT", "REFERENCES"]
    assert [sentence.section_code for sentence in prepared.sentences] == [
        "ABSTRACT",
        "REFERENCES",
    ]
    assert calls == [section.parsed.text for section in prepared.sections]
    assert prepared.sentences[0].char_start == prepared.sections[0].parsed.char_start
    assert prepared.sentences[1].char_start == prepared.sections[1].parsed.char_start
