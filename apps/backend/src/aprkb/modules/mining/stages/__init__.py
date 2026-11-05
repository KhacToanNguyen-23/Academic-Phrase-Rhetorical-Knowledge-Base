"""Deterministic scaffold mining stage registry."""

from aprkb.modules.mining.stages.base import MiningItem, MiningStage
from aprkb.modules.mining.stages.clusterer import Clusterer
from aprkb.modules.mining.stages.construction_matcher import (
    ConstructionMatcher,
    ReportingWithConstruction,
)
from aprkb.modules.mining.stages.epistemic_tagger import EpistemicTagger
from aprkb.modules.mining.stages.frame_normalizer import FrameNormalizer
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.modules.mining.stages.slot_abstractor import SlotAbstractor
from aprkb.modules.mining.stages.todo import TodoMiningStage
from aprkb.policies.loader import PolicyBundle


def build_stages(*, policy_bundle: PolicyBundle) -> list[MiningStage]:
    filter_policy = policy_bundle.mining_filter
    return [
        SentenceFilter(
            min_words=filter_policy.sentence_filter.min_words,
            max_words=filter_policy.sentence_filter.max_words,
            noise=filter_policy.noise_filter,
            syntax=filter_policy.syntax_filter,
        ),
        TodoMiningStage("move_classifier", "FR-06.3"),
        ReportingWithConstruction(
            SlotAbstractor(
                policy_bundle.reporting_verbs,
                policy_bundle.slot_abstraction,
                policy_bundle.lead_ins.lead_ins,
            ),
            ConstructionMatcher(policy_bundle.constructions, policy_bundle.slot_abstraction),
        ),
        EpistemicTagger(policy_bundle.epistemic_markers),
        FrameNormalizer(),
        Clusterer(policy_bundle),
        TodoMiningStage("dedup_matcher", "FR-06.2"),
    ]


__all__ = ["MiningItem", "MiningStage", "build_stages"]
