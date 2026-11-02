"""Guideline gate placeholder using the existing per-journal cache."""

from typing import Protocol
from uuid import UUID

from aprkb.modules.journals.guideline_policy import GuidelinePolicy
from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.gates.base import GateResult, HardGate
from aprkb.modules.recommendation.pattern_view import PatternView


class _GuidelineReader(Protocol):
    def has_mandatory_rules(self, journal_id: UUID) -> bool: ...


class GuidelineGate(HardGate):
    """FR-07.2 / BR-04 / BR-09.

    Mandatory rules must come from verified guidelines, not corpus trends.
    """

    code = "GATE_GUIDELINE"

    def __init__(self, guideline_policy: _GuidelineReader | None = None) -> None:
        self._guideline_policy = guideline_policy or GuidelinePolicy()

    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult:
        del pattern
        if ctx.journal_id is not None and self._guideline_policy.has_mandatory_rules(
            ctx.journal_id
        ):
            # No rule evaluator exists yet; never return a candidate as compliant by default.
            return GateResult(False, "Mandatory guideline cannot yet be evaluated")
        return GateResult(True)
