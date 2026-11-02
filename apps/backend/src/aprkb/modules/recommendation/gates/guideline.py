"""Guideline gate backed by the pluggable rule evaluator registry."""

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from aprkb.modules.journals.guideline_evaluators import (
    GUIDELINE_EVALUATORS,
    GuidelineRuleEvaluator,
)
from aprkb.modules.journals.guideline_policy import GuidelinePolicy
from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.gates.base import GateResult, HardGate
from aprkb.modules.recommendation.pattern_view import PatternView


class _GuidelineReader(Protocol):
    def get(self, journal_id: UUID) -> tuple[dict[str, object], ...]: ...


class GuidelineGate(HardGate):
    """FR-07.2 / BR-04 / BR-09.

    Mandatory rules must come from verified guidelines, not corpus trends.
    A mandatory rule with no registered evaluator fails closed (AT-06).
    """

    code = "GATE_GUIDELINE"

    def __init__(
        self,
        guideline_policy: _GuidelineReader | None = None,
        evaluators: Mapping[str, GuidelineRuleEvaluator] | None = None,
    ) -> None:
        self._guideline_policy = guideline_policy or GuidelinePolicy()
        self._evaluators = evaluators if evaluators is not None else GUIDELINE_EVALUATORS

    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult:
        if ctx.journal_id is None:
            return GateResult(True)
        for rule in self._guideline_policy.get(ctx.journal_id):
            if rule.get("is_mandatory") is not True:
                continue
            rule_type = rule.get("rule_type")
            evaluator = self._evaluators.get(rule_type) if isinstance(rule_type, str) else None
            if evaluator is None:
                # BR-04/BR-09: never treat an unknown mandatory rule as satisfied.
                return GateResult(False, "Mandatory guideline cannot yet be evaluated")
            payload: dict[str, object] = {}
            raw_payload = rule.get("payload")
            if isinstance(raw_payload, dict):
                payload = raw_payload
            result = evaluator.evaluate(pattern, payload, ctx)
            if not result.passed:
                return GateResult(
                    False, result.reason or "Mandatory guideline rule was not satisfied"
                )
        return GateResult(True)
