"""Deterministic scaffold mining stage registry."""

from aprkb.modules.mining.stages.base import MiningItem, MiningStage
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.modules.mining.stages.todo import TodoMiningStage
from aprkb.policies.schemas import MiningFilterPolicy


def build_stages(*, policy: MiningFilterPolicy) -> list[MiningStage]:
    return [
        SentenceFilter(
            min_words=policy.sentence_filter.min_words,
            max_words=policy.sentence_filter.max_words,
            noise=policy.noise_filter,
        ),
        TodoMiningStage("move_classifier", "PRD-6.3"),
        TodoMiningStage("epistemic_tagger", "PRD-6.3"),
        TodoMiningStage("slot_abstractor", "PRD-6.3"),
        TodoMiningStage("frame_normalizer", "PRD-6.3"),
        TodoMiningStage("clusterer", "PRD-6.3"),
        TodoMiningStage("dedup_matcher", "PRD-6.3"),
    ]


__all__ = ["MiningItem", "MiningStage", "build_stages"]
