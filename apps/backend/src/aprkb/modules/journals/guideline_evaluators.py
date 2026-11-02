"""Pluggable evaluators for journal guideline rules.

The rule-type vocabulary and payload schemas belong to the Offline team and are
not agreed yet (AT-06). This module therefore provides only the seam: a protocol,
an empty registry, and no concrete rule types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.pattern_view import PatternView

if TYPE_CHECKING:
    from aprkb.modules.recommendation.gates.base import GateResult


@runtime_checkable
class GuidelineRuleEvaluator(Protocol):
    """Evaluate one guideline rule against a pattern for a journal."""

    rule_type: str

    def evaluate(
        self,
        pattern: PatternView,
        payload: dict[str, object],
        ctx: RecommendationContext,
    ) -> GateResult: ...


class GuidelineEvaluatorRegistry(dict[str, GuidelineRuleEvaluator]):
    """Map ``rule_type`` values to the evaluator that understands them."""

    def register(self, evaluator: GuidelineRuleEvaluator) -> None:
        self[evaluator.rule_type] = evaluator

    def for_rule_type(self, rule_type: str) -> GuidelineRuleEvaluator | None:
        return self.get(rule_type)


# TODO(owner, AT-06): rule types and payload schemas wait for agreement with the
# Offline team. Do not register concrete evaluators here until that contract exists.
GUIDELINE_EVALUATORS = GuidelineEvaluatorRegistry()
