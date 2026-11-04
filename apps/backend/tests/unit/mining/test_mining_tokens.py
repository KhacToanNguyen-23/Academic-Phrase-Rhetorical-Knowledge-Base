"""Mining keeps its phase-1 output independent of stored token features."""

from dataclasses import replace
from uuid import uuid4

from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.nlp.features import TokenFeature
from aprkb.policies.loader import load_policy_bundle


def _signature(item: MiningItem) -> tuple[object, ...]:
    return (
        item.text,
        item.source_sentence_ids,
        item.section_code,
        item.char_start,
        item.previous_text,
        item.slots,
        item.occurrences,
        item.tense,
        item.ownership,
        item.epistemic_strength,
        item.cluster_key,
        item.confidence,
        item.slot_binding_fingerprint,
    )


def test_stored_tokens_do_not_change_mining_candidates() -> None:
    item = MiningItem(
        text="These results suggest that the method is robust to noise.",
        source_sentence_ids=[uuid4()],
        section_code="RESULTS",
    )
    token = TokenFeature(0, 0, 5, "PRON", "DT", "nsubj", 1, "these", "", False)
    with_tokens = replace(item, tokens=(token,))

    def pipeline() -> MiningPipeline:
        return MiningPipeline(stages=build_stages(policy_bundle=load_policy_bundle()))

    assert [_signature(result) for result in pipeline().process([item])] == [
        _signature(result) for result in pipeline().process([with_tokens])
    ]
