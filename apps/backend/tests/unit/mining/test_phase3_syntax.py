"""Phase-3 syntax mining tests using committed, spaCy-free token snapshots."""

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.modules.mining.stages.slot_abstractor import SlotAbstractor
from aprkb.nlp.features import SentenceAnalysis, TokenFeature
from aprkb.nlp.syntax import usable_tokens
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import SyntaxFilterSettings

_FIXTURE = Path(__file__).parents[2] / "fixtures" / "nlp_spike" / "token_snapshots.json"
_SNAPSHOT = json.loads(_FIXTURE.read_text(encoding="utf-8"))
_TOKENS = {
    case["text"]: tuple(TokenFeature.from_json(token) for token in case["analysis"]["tokens"])
    for case in _SNAPSHOT["cases"]
}
_LOCATOR = f"syntax:{_SNAPSHOT['model_name']}:{_SNAPSHOT['model_version']}"
_SLOT_CASES = yaml.safe_load(
    (Path(__file__).parents[2] / "fixtures" / "nlp_spike" / "sentences.yaml").read_text(
        encoding="utf-8"
    )
)


def _item(text: str, *, tokens: tuple[TokenFeature, ...] | None = None) -> MiningItem:
    return MiningItem(
        text=text,
        source_sentence_ids=[uuid4()],
        section_code="RESULTS",
        tokens=tokens,
        locator=_LOCATOR if tokens is not None else None,
    )


def _syntax_item(text: str) -> MiningItem:
    return _item(text, tokens=_TOKENS[text])


def _abstractor() -> SlotAbstractor:
    policy = load_policy_bundle()
    return SlotAbstractor(policy.reporting_verbs, policy.slot_abstraction)


@pytest.mark.parametrize(
    ("text", "frame", "tense"),
    [
        (
            "We show that the gain, as Lee demonstrated, is stable across all tested settings.",
            "[X] show that [Y].",
            "present",
        ),
        (
            "Our experiments clearly show that the proposed model converges faster.",
            "[X] [Y] clearly show that [Z].",
            "present",
        ),
        (
            "The analysis did not reveal that the effect depends on sample size.",
            "[X] did not reveal that [Y].",
            "past",
        ),
        (
            "Previous studies have reported that larger batches reduce variance.",
            "[X] [Y] have reported that [Z].",
            "present_perfect",
        ),
        (
            "It is widely argued that transfer learning reduces annotation cost.",
            "[X] argued that [Y].",
            "present",
        ),
        (
            "Our results surprisingly suggest that the method is robust to noise.",
            "[X] [Y] suggest that [Z].",
            "present",
        ),
    ],
)
def test_syntax_locator_handles_phase3_constructions(text: str, frame: str, tense: str) -> None:
    [result] = MiningPipeline(stages=build_stages(policy_bundle=load_policy_bundle())).process(
        [_syntax_item(text)]
    )

    assert result.text == frame
    assert result.tense == tense
    assert result.locator == _LOCATOR


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (
            "In this paper, we propose a framework that unifies both objectives.",
            "no_that",
        ),
        (
            "Our results show and the authors suggest that the method works reliably.",
            "coordinated_reporting_verbs",
        ),
        (
            "These findings suggest a model that indicates that noise matters.",
            "no_that",
        ),
    ],
)
def test_syntax_locator_rejects_ambiguous_or_relative_constructions(text: str, reason: str) -> None:
    abstractor = _abstractor()

    assert abstractor.extractability_reason(text, _TOKENS[text]) == reason
    assert abstractor._extract(_syntax_item(text)) is None


def test_sentence_filter_uses_finite_verb_and_root_rules() -> None:
    stage = SentenceFilter(
        min_words=1,
        max_words=60,
        syntax=SyntaxFilterSettings(require_finite_verb=True),
    )

    heading = _syntax_item("1. Introduction")
    fragment = _syntax_item("A short fragment.")

    assert stage.reject_reason(heading) == "no_finite_verb"
    assert stage.reject_reason(fragment) == "no_finite_verb"
    source_tokens = _TOKENS["These results suggest that the method is robust to noise."]
    nonverbal_root = tuple(
        replace(token, pos="NOUN") if token.dep == "ROOT" else token for token in source_tokens
    )
    assert (
        stage.reject_reason(
            _item(
                "These results suggest that the method is robust to noise.", tokens=nonverbal_root
            )
        )
        == "root_not_verbal"
    )


def test_invalid_tokens_fall_back_to_regex_and_are_counted() -> None:
    text = "These results suggest that the method is robust to noise."
    tokens = _TOKENS[text]
    abstractor = _abstractor()

    for invalid in (
        (replace(tokens[0], start=-1),) + tokens[1:],
        (replace(tokens[0], dep="ROOT"),) + tokens[1:],
        (),
    ):
        result = abstractor._extract(_item(text, tokens=invalid))
        assert result is not None
        assert result.text == "[X] [Y] suggest that [Z]."

    assert abstractor.syntax_fallback_reasons == {"syntax_invalid_tokens": 3}


def test_repaired_analysis_is_not_used_by_syntax_mining() -> None:
    analysis = SentenceAnalysis(char_start=0, char_end=1, tokens=(), repaired=True)

    assert usable_tokens(analysis) is None


def test_that_clause_can_follow_a_complex_root_subject() -> None:
    text = "The fact that the model converges suggests that the method is robust to noise."
    nested_relative = "These findings suggest a model that indicates that noise matters."
    item = _syntax_item(text)
    stages = build_stages(policy_bundle=load_policy_bundle())
    sentence_filter = next(stage for stage in stages if isinstance(stage, SentenceFilter))
    pipeline = MiningPipeline(stages=stages)

    assert sentence_filter.reject_reason(item) is None
    [result] = pipeline.process([item])
    [occurrence] = result.occurrences
    subject_start, subject_end = occurrence.slot_spans["X"]
    clause_start, clause_end = occurrence.slot_spans["Y"]
    assert text[subject_start:subject_end] == "The fact that the model converges"
    assert text[clause_start:clause_end] == "the method is robust to noise"
    assert result.text == "[X] suggests that [Y]."
    assert pipeline.process([_syntax_item(nested_relative)]) == []


def test_aux_attached_that_and_subject_are_normalized_to_clause_head() -> None:
    text = "These findings may indicate that the baseline was undertrained."
    stages = build_stages(policy_bundle=load_policy_bundle())
    [result] = MiningPipeline(stages=stages).process([_syntax_item(text)])
    [occurrence] = result.occurrences
    start, end = occurrence.slot_spans["Z"]

    assert result.text == "[X] [Y] may indicate that [Z]."
    assert text[start:end] == "the baseline was undertrained"


def test_regex_cluster_key_is_unchanged_and_syntax_key_is_scoped() -> None:
    text = "These results suggest that the method is robust to noise."
    pipeline = MiningPipeline(stages=build_stages(policy_bundle=load_policy_bundle()))
    [regex_result] = pipeline.process([_item(text)])
    [syntax_result] = pipeline.process([_syntax_item(text)])

    assert regex_result.locator is None
    assert syntax_result.locator == _LOCATOR
    assert regex_result.cluster_key != syntax_result.cluster_key


def test_slot_case_parity_has_a_reviewed_allow_list() -> None:
    abstractor = _abstractor()
    differences: dict[int, str] = {}
    outcomes: dict[int, str] = {}
    parity_cases = [
        *_SLOT_CASES["slot_cases"],
        "The fact that the model converges suggests that the method is robust to noise.",
    ]
    for index, text in enumerate(parity_cases, start=1):
        regex = abstractor._extract(_item(text))
        syntax = abstractor._extract(_syntax_item(text))
        if regex is None and syntax is None:
            outcomes[index] = "neither"
            continue
        if regex is None:
            outcomes[index] = "only_syntax"
            differences[index] = "syntax uses ROOT show instead of a longer reporting form"
            continue
        if syntax is None:
            outcomes[index] = "only_regex"
            differences[index] = (
                "strict direct marker check rejects the model's non-direct that attachment"
            )
            continue
        assert regex.text == syntax.text
        same = (
            regex.text,
            regex.slots,
            regex.tense,
            regex.ownership,
            regex.occurrences[0].slot_spans,
        ) == (
            syntax.text,
            syntax.slots,
            syntax.tense,
            syntax.ownership,
            syntax.occurrences[0].slot_spans,
        )
        outcomes[index] = "both_equal" if same else "both_differ"
        if not same:
            differences[index] = (
                "syntax uses finite passive auxiliary tense and narrows subject to It"
                if index == 6
                else "syntax subtree slot span excludes trailing sentence punctuation"
            )

    assert outcomes == {
        1: "both_differ",
        2: "only_syntax",
        3: "only_syntax",
        4: "both_differ",
        5: "both_differ",
        6: "both_differ",
        7: "both_differ",
        8: "neither",
        9: "both_differ",
        10: "neither",
        11: "both_differ",
    }
    assert differences == {
        1: "syntax subtree slot span excludes trailing sentence punctuation",
        2: "syntax uses ROOT show instead of a longer reporting form",
        3: "syntax uses ROOT show instead of a longer reporting form",
        4: "syntax subtree slot span excludes trailing sentence punctuation",
        5: "syntax subtree slot span excludes trailing sentence punctuation",
        6: "syntax uses finite passive auxiliary tense and narrows subject to It",
        7: "syntax subtree slot span excludes trailing sentence punctuation",
        9: "syntax subtree slot span excludes trailing sentence punctuation",
        11: "syntax subtree slot span excludes trailing sentence punctuation",
    }
