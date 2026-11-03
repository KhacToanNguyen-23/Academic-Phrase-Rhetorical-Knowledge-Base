"""Pure recommendation scorer interface."""

from abc import ABC, abstractmethod
from typing import ClassVar

from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.pattern_view import PatternView


class Scorer(ABC):
    key: ClassVar[str]

    @abstractmethod
    def score(self, pattern: PatternView, ctx: RecommendationContext) -> float | None: ...
