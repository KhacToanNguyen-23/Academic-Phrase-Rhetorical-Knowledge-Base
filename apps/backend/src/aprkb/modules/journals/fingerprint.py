"""Journal fingerprint computation stub."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aprkb.modules.journals.models import JournalProfile


class JournalFingerprintService:
    def compute(self, journal: JournalProfile) -> Sequence[float] | None:
        """Return no vector until the fingerprint algorithm is specified."""
        del journal
        # TODO(owner, FR-07.6): implement fingerprinting after data and algorithm approval.
        return None
