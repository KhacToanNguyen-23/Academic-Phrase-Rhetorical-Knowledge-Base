"""Pure recommendation gate interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.pattern_view import PatternView


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reason: str | None = None


class HardGate(ABC):
    code: ClassVar[str]

    @abstractmethod
    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult: ...
