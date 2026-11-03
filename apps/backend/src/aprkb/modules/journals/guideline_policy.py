"""Small per-journal guideline cache; rule evaluation remains TODO(owner, AT-06)."""

from uuid import UUID


class GuidelinePolicy:
    """Cache immutable guideline payloads by journal for request-time gates."""

    def __init__(self) -> None:
        self._cache: dict[UUID, tuple[dict[str, object], ...]] = {}

    def get(self, journal_id: UUID) -> tuple[dict[str, object], ...]:
        # TODO(owner, AT-06): populate active rules and define cache invalidation.
        return self._cache.get(journal_id, ())

    def set(self, journal_id: UUID, rules: tuple[dict[str, object], ...]) -> None:
        self._cache[journal_id] = rules

    def has_mandatory_rules(self, journal_id: UUID) -> bool:
        return any(rule.get("is_mandatory") is True for rule in self.get(journal_id))
