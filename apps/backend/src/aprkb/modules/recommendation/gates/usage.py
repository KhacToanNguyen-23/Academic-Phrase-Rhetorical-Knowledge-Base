"""Usage constraints from the approved pattern version."""

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.gates.base import GateResult, HardGate
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.policies.evidence import EvidencePolicy


class EvidenceMinimumGate(HardGate):
    code = "GATE_EVIDENCE_MIN"

    def __init__(self, policy: EvidencePolicy) -> None:
        self._policy = policy

    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult:
        if ctx.evidence_level is None or pattern.evidence_min is None:
            return GateResult(True)
        passed = self._policy.meets_minimum(ctx.evidence_level, pattern.evidence_min)
        return GateResult(passed, None if passed else "Declared evidence is below pattern minimum")


class ForbiddenContextGate(HardGate):
    code = "GATE_FORBIDDEN_CONTEXT"

    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult:
        # TODO(owner, FR-02.4): confirm literal section, genre, or claim code semantics.
        requested = {ctx.section_code, ctx.genre_code, ctx.claim_type} - {None}
        passed = not requested.intersection(pattern.forbidden_contexts)
        return GateResult(passed, None if passed else "Requested context is forbidden")
