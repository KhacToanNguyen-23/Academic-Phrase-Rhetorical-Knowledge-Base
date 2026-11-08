"""Hybrid sentence boundaries and stored token-feature invariants."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from aprkb.modules.corpus.sentence_splitter import boundary_candidates
from aprkb.nlp import SentenceAnalysis, SpacyEngine
from aprkb.policies.loader import load_policy_bundle
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
    assert info.boundary_policy_version == load_policy_bundle().sentence_rules.version


def test_first_sentence_boundary_is_rule_start() -> None:
    engine = SpacyEngine()

    for case in _cases():
        analyses = engine.analyze(case["text"])
        assert analyses[0].boundary_source == "rule:start"


def test_whitespace_head_repair_is_recorded_in_json() -> None:
    space = SimpleNamespace(i=1, is_space=True, text=" ", idx=5, lemma_=" ")
    word = SimpleNamespace(
        i=0,
        is_space=False,
        text="Word",
        idx=0,
        head=space,
        dep_="dep",
        pos_="NOUN",
        tag_="NN",
        lemma_="word",
        morph="",
    )

    class FakeSentence:
        start_char = 0
        end_char = 4
        text = "Word"

        def __iter__(self):
            return iter((word,))

    doc = SimpleNamespace(text="Word")
    sentence = FakeSentence()

    analysis = SpacyEngine._analysis_from_sentence(doc, sentence, {}, is_first=True)

    assert analysis.repaired
    assert analysis.tokens[0].dep == "ROOT"
    assert analysis.to_json()["repaired"] is True
    assert SentenceAnalysis.from_json(analysis.to_json()).repaired


def test_hybrid_never_starts_a_sentence_outside_a_rule_candidate() -> None:
    engine = SpacyEngine()
    for case in _cases():
        text = case["text"]
        doc = engine._nlp(text)
        candidates = {candidate.offset for candidate in boundary_candidates(text)}
        first_content = next(token.idx for token in doc if not token.is_space)

        assert {token.idx for token in doc if token.is_sent_start} <= candidates | {first_content}


def test_hybrid_preserves_cases_solved_by_regex_or_round_two_web() -> None:
    engine = SpacyEngine()
    for index, case in enumerate(_cases(), start=1):
        if index in {8, 12}:
            continue
        actual = [item.to_sentence_span(case["text"]).text for item in engine.analyze(case["text"])]
        assert actual == case["expected"]


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
