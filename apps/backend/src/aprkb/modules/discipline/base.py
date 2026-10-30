"""Interfaces for journal discipline classification."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from aprkb.modules.journals.models import JournalProfile


class DisciplineSource(Protocol):
    def classify_journal(self, journal: JournalProfile) -> list[tuple[str, float]] | None: ...
