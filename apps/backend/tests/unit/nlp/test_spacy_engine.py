"""TODO(owner, FR-06.2): spike only; not wired into ingest or mining."""

from pathlib import Path

import pytest
import yaml

from aprkb.nlp import SpacyEngine
from scripts.nlp_spike_compare import _syntax_spans

spacy = pytest.importorskip("spacy")
pytest.importorskip("en_core_web_sm")


_FIXTURE = Path(__file__).parents[2] / "fixtures" / "nlp_spike" / "sentences.yaml"


def _cases() -> list[dict[str, object]]:
    with _FIXTURE.open(encoding="utf-8") as fixture:
        return yaml.safe_load(fixture)["cases"]


def test_token_offsets_match_source_for_every_fixture_case() -> None:
    engine = SpacyEngine()
    for case in _cases():
        text = case["text"]
        doc = engine._nlp(text)
        spacy_tokens = {(token.idx, token.idx + len(token.text)): token.text for token in doc}
        for analysis in engine.analyze(text):
            for token in analysis.tokens:
                absolute_span = (
                    analysis.char_start + token.start,
                    analysis.char_start + token.end,
                )
                assert spacy_tokens[absolute_span] == text[slice(*absolute_span)]


def test_heads_stay_inside_sentence_with_one_root() -> None:
    engine = SpacyEngine()
    for case in _cases():
        for analysis in engine.analyze(case["text"]):
            assert all(0 <= token.head < len(analysis.tokens) for token in analysis.tokens)
            assert sum(token.dep == "ROOT" for token in analysis.tokens) == 1


def test_blank_line_is_a_sentence_boundary() -> None:
    case = next(case for case in _cases() if "\n\n" in case["text"])
    analysis = SpacyEngine().analyze(case["text"])
    assert [item.to_sentence_span(case["text"]).text for item in analysis] == [
        "First paragraph ends here.",
        "Second paragraph starts here.",
    ]


def test_blank_line_overrides_abbreviation_guard() -> None:
    text = "Dr.\n\nNext sentence."
    assert [item.to_sentence_span(text).text for item in SpacyEngine().analyze(text)] == [
        "Dr.",
        "Next sentence.",
    ]


def test_tokenizer_splits_unspaced_sentence_boundary() -> None:
    text = "CNNs.Our approach differs."
    engine = SpacyEngine()
    assert [token.text for token in engine._nlp(text)[:3]] == ["CNNs", ".", "Our"]
    assert [item.to_sentence_span(text).text for item in engine.analyze(text)] == [
        "CNNs.",
        "Our approach differs.",
    ]


def test_info_reports_real_versions_and_schema() -> None:
    info = SpacyEngine().info
    assert info.engine == "spacy"
    assert info.spacy_version == spacy.__version__
    assert info.model_name == "en_core_web_sm"
    assert info.model_version
    assert info.schema_version == 1


def test_syntax_probe_uses_only_direct_root_dependencies() -> None:
    text = "These results suggest that the method is robust to noise."
    engine = SpacyEngine()
    subject_kind, subject, clause, has_that_mark = _syntax_spans(engine._nlp(text), text)
    assert subject_kind == "nsubj"
    assert subject == "These results"
    assert clause == "that the method is robust to noise"
    assert has_that_mark


def test_question_and_exclamation_boundaries_respect_parentheses() -> None:
    engine = SpacyEngine()
    text = "Does this hold? We argue it does! Moreover, see Eq. (2)."
    assert [item.to_sentence_span(text).text for item in engine.analyze(text)] == [
        "Does this hold?",
        "We argue it does!",
        "Moreover, see Eq. (2).",
    ]
    quoted = 'The question ("does it scale?") remains open.'
    assert [item.to_sentence_span(quoted).text for item in engine.analyze(quoted)] == [quoted]
