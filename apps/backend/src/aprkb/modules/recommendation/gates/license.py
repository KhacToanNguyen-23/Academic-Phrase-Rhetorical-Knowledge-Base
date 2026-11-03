"""Enforce display rights for mined patterns."""

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.gates.base import GateResult, HardGate
from aprkb.modules.recommendation.pattern_view import PatternView


class LicenseGate(HardGate):
    """FR-07.2 / BR-01 / BR-10: fail closed unless the pattern source permits display."""

    code = "GATE_LICENSE"

    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult:
        del ctx
        if pattern.source_type == "authored":
            return GateResult(True)
        if pattern.source_type == "mined" and pattern.license_allows_display:
            return GateResult(True)
        if pattern.source_type == "mined":
            reason = "Source license does not allow display"
        else:
            reason = "Pattern provenance type is unknown"
        return GateResult(False, reason)
