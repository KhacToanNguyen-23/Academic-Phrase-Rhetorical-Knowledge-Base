"""Exclude retired patterns."""

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.gates.base import GateResult, HardGate
from aprkb.modules.recommendation.pattern_view import PatternView


class RetiredGate(HardGate):
    """FR-07.2: retired patterns are excluded before ranking."""

    code = "GATE_RETIRED"

    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult:
        del ctx
        passed = pattern.status != "retired"
        return GateResult(passed, None if passed else "Pattern is retired")
