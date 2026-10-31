"""Match the requested intent and section."""

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.gates.base import GateResult, HardGate
from aprkb.modules.recommendation.pattern_view import PatternView


class IntentSectionGate(HardGate):
    code = "GATE_INTENT_SECTION"

    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult:
        passed = (
            pattern.intent_code == ctx.intent_code and ctx.section_code in pattern.allowed_sections
        )
        return GateResult(passed, None if passed else "Pattern does not match intent and section")
