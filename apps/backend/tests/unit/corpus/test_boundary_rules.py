"""Character-level boundary candidates shared by regex and spaCy."""

from pathlib import Path

import pytest
import yaml

from aprkb.modules.corpus.sentence_splitter import (
    BoundaryDecision,
    boundary_candidates,
    split_sentences,
)
from aprkb.policies.loader import load_policy_bundle

_FIXTURE = Path(__file__).parents[2] / "fixtures" / "nlp_spike" / "sentences.yaml"


def _cases() -> list[dict[str, object]]:
    with _FIXTURE.open(encoding="utf-8") as fixture:
        return yaml.safe_load(fixture)["cases"]


def test_all_dev_fixture_boundaries_are_character_offsets() -> None:
    rules = load_policy_bundle().sentence_rules
    for case in _cases():
        text = case["text"]
        candidates = boundary_candidates(text, rules)
        assert all(0 < candidate.offset <= len(text) for candidate in candidates)
        assert [span.text for span in split_sentences(text, rules=rules)]


@pytest.mark.parametrize(
    ("text", "decision", "rule"),
    [
        ("First.\n\nSecond.", BoundaryDecision.SPLIT, "blank_line"),
        ("1. Introduction\nDeep learning.", BoundaryDecision.SPLIT, "heading_line"),
        ("The claim (see Fig. 2. Next.)", BoundaryDecision.NO_SPLIT, "open_bracket"),
        ("No. 5 participants.", BoundaryDecision.NO_SPLIT, "abbrev_digit"),
        ("Approx. 40 samples.", BoundaryDecision.NO_SPLIT, "abbrev_digit"),
        ("J. Smith reports gains.", BoundaryDecision.NO_SPLIT, "initial"),
        ("Does this hold? We test.", BoundaryDecision.SPLIT, "question_exclamation"),
        ("CNNs.Our approach.", BoundaryDecision.SPLIT, "unspaced"),
        ("The result. However, we agree.", BoundaryDecision.SPLIT, "sentence_punctuation"),
        ("Lee et al. Our method.", BoundaryDecision.SPLIT, "abbrev_starter"),
        ("The type A. Results follow.", BoundaryDecision.UNSURE, "unsure_initial"),
    ],
)
def test_boundary_rule_priority(text: str, decision: BoundaryDecision, rule: str) -> None:
    candidates = boundary_candidates(text, load_policy_bundle().sentence_rules)

    assert any(
        candidate.decision is decision and candidate.rule == rule for candidate in candidates
    )


def test_sentence_rules_policy_is_versioned_and_loaded() -> None:
    policy = load_policy_bundle().sentence_rules

    assert policy.version == "0.1.0"
    assert "latency" in policy.sentence_starters
    assert "ms" in policy.unit_tokens
    assert policy.heading_max_chars == 120
