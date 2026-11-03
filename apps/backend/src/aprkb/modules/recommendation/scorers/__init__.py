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


def build_scorers(
    *, discipline_source: DisciplineSource, evidence_policy: EvidencePolicy
) -> list[Scorer]:
    return [
        DisciplineScorer(discipline_source),
        JournalGenreScorer(),
        EvidenceScorer(evidence_policy),
        LinguisticScorer(),
        ProvenanceScorer(),
    ]


__all__ = ["Scorer", "aggregate_scores", "build_scorers"]
