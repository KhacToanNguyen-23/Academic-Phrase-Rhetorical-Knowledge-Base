"""Self-authored regression corpus for reporting-verb slot extraction."""

from uuid import uuid4

import pytest

from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.policies.loader import load_policy_bundle


def _pipeline() -> MiningPipeline:
    return MiningPipeline(stages=build_stages(policy_bundle=load_policy_bundle()))


def _case(verb: str, past: str, perfect: str) -> list[tuple[str, str, str]]:
    return [
        (
            f"Our results {verb} that the mock system improves retrieval quality.",
            f"[X] [Y] {verb} that [Z].",
            "present",
        ),
        (
            f"Our results {past} that the mock system improves retrieval quality.",
            f"[X] [Y] {past} that [Z].",
            "past",
        ),
        (
            f"Our results have {perfect} that the mock system improves retrieval quality.",
            f"[X] [Y] have {perfect} that [Z].",
            "present_perfect",
        ),
    ]


_NEW_VERB_CASES = [
    case
    for values in (
        ("reveal", "revealed", "revealed"),
        ("confirm", "confirmed", "confirmed"),
        ("imply", "implied", "implied"),
        ("highlight", "highlighted", "highlighted"),
        ("observe", "observed", "observed"),
        ("conclude", "concluded", "concluded"),
        ("argue", "argued", "argued"),
        ("note", "noted", "noted"),
        ("establish", "established", "established"),
        ("verify", "verified", "verified"),
        ("state", "stated", "stated"),
        ("claim", "claimed", "claimed"),
        ("assume", "assumed", "assumed"),
        ("propose", "proposed", "proposed"),
    )
    for case in _case(*values)
]


@pytest.mark.parametrize("sentence, expected_frame, expected_tense", _NEW_VERB_CASES)
def test_new_reporting_verbs_cover_each_tense(
    sentence: str, expected_frame: str, expected_tense: str
) -> None:
    result = _pipeline().process([MiningItem(text=sentence, source_sentence_ids=[uuid4()])])

    assert len(result) == 1
    assert result[0].text == expected_frame
    assert result[0].tense == expected_tense


@pytest.mark.parametrize(
    ("sentence", "expected_frame"),
    [
        (
            "Our results do not reveal that the mock system improves retrieval quality.",
            "[X] [Y] do not reveal that [Z].",
        ),
        (
            "Our results may confirm that the mock system improves retrieval quality.",
            "[X] [Y] may confirm that [Z].",
        ),
        (
            "Our results could imply that the mock system improves retrieval quality.",
            "[X] [Y] could imply that [Z].",
        ),
        (
            "Our results never state that the mock system improves retrieval quality.",
            "[X] [Y] never state that [Z].",
        ),
        (
            "Our results did not show that the mock system improves retrieval quality.",
            "[X] [Y] did not show that [Z].",
        ),
        (
            "Previous studies confirm that the mock system improves retrieval quality.",
            "[X] [Y] confirm that [Z].",
        ),
        (
            "The study confirms that the mock system improves retrieval quality.",
            "[X] confirms that [Y].",
        ),
        (
            "Our results reveal that the mock system improves retrieval quality [12].",
            "[X] [Y] reveal that [Z].",
        ),
        (
            "Our results confirm that the mock system improves retrieval quality (Smith, 2020).",
            "[X] [Y] confirm that [Z].",
        ),
    ],
)
def test_modifiers_ownership_and_citations_remain_literal_or_typed(
    sentence: str, expected_frame: str
) -> None:
    result = _pipeline().process([MiningItem(text=sentence, source_sentence_ids=[uuid4()])])

    assert len(result) == 1
    assert result[0].text == expected_frame


@pytest.mark.parametrize(
    "sentence",
    [
        "The mock system improves retrieval quality today.",
        "Our results reveal the mock system improves retrieval quality.",
        "Reveal that the mock system improves retrieval quality.",
        (
            "The carefully designed mock retrieval experiment with several independent checks "
            "reveals that the mock system improves quality."
        ),
        "Our results reveal that cold.",
        "That approach shows a gain.",
        "These reveal that the mock system improves retrieval quality.",
    ],
)
def test_unsupported_or_ambiguous_constructions_return_none(sentence: str) -> None:
    assert _pipeline().process([MiningItem(text=sentence, source_sentence_ids=[uuid4()])]) == []
