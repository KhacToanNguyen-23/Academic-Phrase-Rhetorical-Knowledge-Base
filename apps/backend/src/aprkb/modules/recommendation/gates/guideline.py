"""Guideline gate placeholder using the existing per-journal cache."""

from typing import Protocol
from uuid import UUID

from aprkb.modules.journals.guideline_policy import GuidelinePolicy
from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.gates.base import GateResult, HardGate
from aprkb.modules.recommendation.pattern_view import PatternView


class _GuidelineReader(Protocol):
    def get(self, journal_id: UUID) -> tuple[dict[str, object], ...]: ...


class GuidelineGate(HardGate):
    code = "GATE_GUIDELINE"

    def __init__(self, guideline_policy: _GuidelineReader | None = None) -> None:
        self._guideline_policy = guideline_policy or GuidelinePolicy()

    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult:
        del pattern
        if ctx.journal_id is not None:
            self._guideline_policy.get(ctx.journal_id)
        # TODO(owner, AT-06): implement cached mandatory guideline rule evaluation.
        return GateResult(True)
