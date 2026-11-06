"""Small deterministic scaffold scorers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.recommendation.scorers.base import Scorer
from aprkb.policies.evidence import EvidencePolicy
from aprkb.shared.keywords import keyword_tokens

if TYPE_CHECKING:
    from aprkb.modules.discipline.base import DisciplineSource


class IntentScorer(Scorer):
    key = "intent"

    def __init__(self, *, same_move: float) -> None:
        self._same_move = same_move

    def score(self, pattern: PatternView, ctx: RecommendationContext) -> float | None:
        if ctx.intent_code:
            return 1.0 if ctx.intent_code == pattern.intent_code else None
        if ctx.move_code and ctx.move_code == pattern.move_code:
            return self._same_move
        return None


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
        if not ctx.evidence_level:
            return None
        return self._evidence_policy.alignment_score(
            ctx.claim_type or pattern.claim_type or "",
            ctx.evidence_level,
            pattern.epistemic_strength or "",
        )


class LinguisticScorer(Scorer):
    key = "linguistic"

    def score(self, pattern: PatternView, ctx: RecommendationContext) -> float | None:
        if not ctx.query:
            return None
        keywords = keyword_tokens(ctx.query)
        if not keywords:
            return None
        frame_words = keyword_tokens(pattern.canonical_frame)
        return len(keywords & frame_words) / len(keywords)


class ProvenanceScorer(Scorer):
    key = "provenance"

    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores

    def score(self, pattern: PatternView, ctx: RecommendationContext) -> float:
        del ctx
        return self._scores[pattern.source_type]
