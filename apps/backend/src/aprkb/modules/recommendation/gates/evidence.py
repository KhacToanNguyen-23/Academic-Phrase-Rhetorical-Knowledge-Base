"""Fail-closed evidence gate backed by the shared EvidencePolicy."""

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.gates.base import GateResult, HardGate
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.policies.evidence import EvidencePolicy


class EvidenceGate(HardGate):
    """FR-07.2 / BR-03: a candidate's epistemic strength cannot exceed supplied evidence."""

    code = "GATE_EVIDENCE"

    def __init__(self, evidence_policy: EvidencePolicy) -> None:
        self._evidence_policy = evidence_policy

    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult:
        if not ctx.evidence_level:
            return GateResult(True)
        claim_type = ctx.claim_type or pattern.claim_type or ""
        if not self._evidence_policy.is_allowed(
            claim_type, ctx.evidence_level, pattern.epistemic_strength or ""
        ):
            return GateResult(False, "Evidence is missing, unknown, or insufficient")
        return GateResult(True)
