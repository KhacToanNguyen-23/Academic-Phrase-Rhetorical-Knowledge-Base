"""Shared parse, section-detection, and per-section sentence analysis for ingest."""

from collections.abc import Callable
from dataclasses import dataclass

from aprkb.modules.corpus.parsers.base import DocumentParser, ParsedDocument, ParsedSection
from aprkb.modules.corpus.section_detector import SectionDetector
from aprkb.policies.schemas import SectionHeadingsPolicy

SectionAnalysis = tuple[str, int, int, dict[str, object] | None, str]
SectionAnalyser = Callable[[str], list[SectionAnalysis]]


@dataclass(frozen=True)
class IngestedSection:
    parsed: ParsedSection
    section_code: str | None


@dataclass(frozen=True)
class IngestedSentence:
    section_order: int
    section_code: str | None
    text: str
    char_start: int
    char_end: int
    nlp_features: dict[str, object] | None
    boundary_source: str


@dataclass(frozen=True)
class IngestedDocument:
    parsed: ParsedDocument
    sections: tuple[IngestedSection, ...]
    sentences: tuple[IngestedSentence, ...]


def parse_and_analyze(
    parser: DocumentParser,
    blob: bytes,
    *,
    section_headings: SectionHeadingsPolicy,
    analyse_section: SectionAnalyser,
) -> IngestedDocument:
    """Run the same parser → section detector → per-section analyzer path as worker ingest."""
    parsed = parser.parse(blob)
    section_codes = SectionDetector(section_headings).detect(parsed.sections)
    sections: list[IngestedSection] = []
    sentences: list[IngestedSentence] = []
    for section, code in zip(parsed.sections, section_codes, strict=True):
        sections.append(IngestedSection(parsed=section, section_code=code))
        for text, start, end, features, boundary_source in analyse_section(section.text):
            sentences.append(
                IngestedSentence(
                    section_order=section.order,
                    section_code=code,
                    text=text,
                    char_start=section.char_start + start,
                    char_end=section.char_start + end,
                    nlp_features=features,
                    boundary_source=boundary_source,
                )
            )
    return IngestedDocument(parsed=parsed, sections=tuple(sections), sentences=tuple(sentences))
