"""Only approved patterns can be recommended."""

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.gates.base import GateResult, HardGate
from aprkb.modules.recommendation.pattern_view import PatternView


class ApprovalGate(HardGate):
    """FR-07.2 / BR-01: only approved patterns may enter recommendation results."""

    code = "GATE_APPROVAL"

    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult:
        del ctx
        passed = pattern.status == "approved"
        return GateResult(passed, None if passed else "Pattern is not approved")
