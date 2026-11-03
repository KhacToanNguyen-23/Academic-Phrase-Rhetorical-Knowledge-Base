"""Recommendation scorer registry."""

from aprkb.modules.discipline.base import DisciplineSource
from aprkb.modules.recommendation.scorers.aggregator import aggregate_scores
from aprkb.modules.recommendation.scorers.base import Scorer
from aprkb.modules.recommendation.scorers.implementations import (
    DisciplineScorer,
    EvidenceScorer,
    JournalGenreScorer,
    LinguisticScorer,
    ProvenanceScorer,
)
from aprkb.policies.evidence import EvidencePolicy
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import RankingWeightsPolicy


def build_scorers(
    *,
    discipline_source: DisciplineSource,
    evidence_policy: EvidencePolicy,
    ranking_policy: RankingWeightsPolicy | None = None,
) -> list[Scorer]:
    ranking_policy = ranking_policy or load_policy_bundle().ranking_weights
    return [
        DisciplineScorer(discipline_source),
        JournalGenreScorer(),
        EvidenceScorer(evidence_policy),
        LinguisticScorer(),
        ProvenanceScorer(ranking_policy.provenance_scores),
    ]


__all__ = ["Scorer", "aggregate_scores", "build_scorers"]
