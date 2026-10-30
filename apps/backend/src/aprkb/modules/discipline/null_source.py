"""Placeholder discipline source used until the OpenAlex adapter is implemented."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aprkb.modules.journals.models import JournalProfile


class NullDisciplineSource:
    def classify_journal(self, journal: JournalProfile) -> list[tuple[str, float]] | None:
        """Return no classification while the external source remains out of scope."""
        del journal
        return None
