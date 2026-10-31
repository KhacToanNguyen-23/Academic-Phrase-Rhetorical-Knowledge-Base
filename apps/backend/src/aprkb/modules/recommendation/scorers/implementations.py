"""Small deterministic scaffold scorers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.recommendation.scorers.base import Scorer
from aprkb.policies.evidence import EvidencePolicy

if TYPE_CHECKING:
    from aprkb.modules.discipline.base import DisciplineSource


class IntentScorer(Scorer):
    key = "intent"

    def score(self, pattern: PatternView, ctx: RecommendationContext) -> float:
        return 1.0 if pattern.intent_code == ctx.intent_code else 0.0


class DisciplineScorer(Scorer):
    key = "discipline"

    def __init__(self, source: DisciplineSource) -> None:
        self._source = source

    def score(self, pattern: PatternView, ctx: RecommendationContext) -> None:
        del pattern, ctx
        # TODO(owner, PRD-03): score affinities after journal classifications are available.
        return None


class JournalGenreScorer(Scorer):
    key = "journal_genre"

    def score(self, pattern: PatternView, ctx: RecommendationContext) -> None:
        del pattern, ctx
        # TODO(owner, FR-07.6): score journal genre after approved fingerprint logic exists.
        return None


class EvidenceScorer(Scorer):
    key = "evidence"

    def __init__(self, evidence_policy: EvidencePolicy) -> None:
        self._evidence_policy = evidence_policy

    def score(self, pattern: PatternView, ctx: RecommendationContext) -> float | None:
        claim_type = ctx.claim_type or pattern.claim_type
        if not ctx.evidence_level:
            return None
        return float(
            self._evidence_policy.is_allowed(
                claim_type, ctx.evidence_level, pattern.epistemic_strength
            )
        )


class LinguisticScorer(Scorer):
    key = "linguistic"

    def score(self, pattern: PatternView, ctx: RecommendationContext) -> float:
        del pattern, ctx
        # TODO(owner, PRD-6.1): replace the neutral score with an approved linguistic scorer.
        return 0.5


class ProvenanceScorer(Scorer):
    key = "provenance"

    def score(self, pattern: PatternView, ctx: RecommendationContext) -> float:
        del ctx
        return 1.0 if pattern.source_type == "authored" else 0.7
