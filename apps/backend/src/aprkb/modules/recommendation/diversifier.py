"""Recommendation diversification hook; scaffold preserves ranking order."""

from collections.abc import Sequence
from typing import Protocol, TypeVar

T = TypeVar("T")


class Diversifier(Protocol[T]):
    def diversify(self, items: Sequence[T]) -> list[T]: ...


class PassThroughDiversifier:
    def diversify(self, items: Sequence[T]) -> list[T]:
        # TODO(owner, FR-07.6): implement diversity constraints after journal data exists.
        return list(items)
