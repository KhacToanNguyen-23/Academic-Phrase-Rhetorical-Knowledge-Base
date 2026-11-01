"""Noise filtering in the sentence filter stage (phase 01, spec 3.1b)."""

from uuid import uuid4

import pytest

from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter, noise_reason
from aprkb.policies.loader import load_policy_bundle

_NOISE = load_policy_bundle().mining_filter.noise_filter


@pytest.mark.parametrize(
    ("text", "section", "reason"),
    [
        (
            "The authors thank the reviewers for helpful comments.",
            "BACK_MATTER",
            "excluded_section",
        ),
        ("A survey of methods in learning systems, volume four.", "REFERENCES", "excluded_section"),
        ("Method | Accuracy | Recall | Time", "RESULTS", "table_row"),
        ("Fig. 3. Accuracy of each model on the held-out split.", "RESULTS", "caption"),
        ("Table 2: Settings used in all training runs.", "METHODS", "caption"),
        ("where ∑ α_i = 1 and β ≤ γ + δ holds for each i", "METHODS", "math"),
        ("0.91 0.88 0.93 0.87 0.90 and 0.89", "RESULTS", "numeric"),
    ],
)
def test_noise_reasons(text: str, section: str | None, reason: str) -> None:
    assert noise_reason(text, section, _NOISE) == reason


@pytest.mark.parametrize(
    "text",
    [
        "Table 3 shows that the proposed model improves recall on rare classes.",
        "These results suggest that staleness matters more than client count.",
        "The method reached 0.93 accuracy after 20 rounds of training.",
    ],
)
def test_ordinary_sentences_are_kept(text: str) -> None:
    assert noise_reason(text, "RESULTS", _NOISE) is None
    assert noise_reason(text, None, _NOISE) is None


def test_stage_drops_noise_and_keeps_section_code() -> None:
    stage = SentenceFilter(min_words=3, max_words=60, noise=_NOISE)
    kept = MiningItem(
        text="These findings indicate that the filter works well [4].",
        source_sentence_ids=[uuid4()],
        section_code="DISCUSSION",
    )
    dropped = MiningItem(
        text="Fig. 1. Overview of the pipeline and its stages.",
        source_sentence_ids=[uuid4()],
        section_code="METHODS",
    )

    results = stage.process([kept, dropped])

    assert [(item.text, item.section_code) for item in results] == [
        ("These findings indicate that the filter works well.", "DISCUSSION")
    ]
    assert stage.reject_reason(dropped) == "caption"
