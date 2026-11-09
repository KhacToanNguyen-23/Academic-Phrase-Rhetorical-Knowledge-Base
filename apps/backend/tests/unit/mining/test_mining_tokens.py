"""Mining reads valid stored token features without changing the candidate contract."""

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.nlp.features import TokenFeature
from aprkb.policies.loader import load_policy_bundle


def test_stored_tokens_keep_the_candidate_frame_shape_and_regex_path() -> None:
    item = MiningItem(
        text="These results suggest that the method is robust to noise.",
        source_sentence_ids=[uuid4()],
        section_code="RESULTS",
    )
    fixture = Path(__file__).parents[2] / "fixtures" / "nlp_spike" / "token_snapshots.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    snapshot = next(case for case in payload["cases"] if case["text"] == item.text)
    tokens = tuple(TokenFeature.from_json(token) for token in snapshot["analysis"]["tokens"])
    with_tokens = replace(item, tokens=tokens, locator="syntax:en_core_web_sm:3.8.0")

    def pipeline() -> MiningPipeline:
        return MiningPipeline(stages=build_stages(policy_bundle=load_policy_bundle()))

    [regex_result] = pipeline().process([item])
    [syntax_result] = pipeline().process([with_tokens])

    assert regex_result.text == "[X] [Y] suggest that [Z]."
    assert syntax_result.text == "[X] [Y] suggest that [Z]."
    [syntax_occurrence] = syntax_result.occurrences
    start, end = syntax_occurrence.slot_spans["Z"]
    assert item.text[start:end] == "the method is robust to noise"
