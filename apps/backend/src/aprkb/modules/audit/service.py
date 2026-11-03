"""Audit successful state changes only, within their data transaction.

Failed requests, 501 responses, and read-only POSTs are not audited. A rolled-back
write drops its audit event with it. Snapshots exclude keys, secrets, and full text.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.models import AuditEvent

_REDACTED_KEYS = {
    "apikey",
    "key",
    "keyhash",
    "token",
    "accesstoken",
    "authorization",
    "password",
    "secret",
    "secretkey",
    "clientsecret",
    "rawtext",
    "fulltext",
    "articletext",
    "manuscript",
    "content",
    "body",
    "text",
}


def _safe_snapshot(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _safe_snapshot(item)
            for key, item in value.items()
            if "".join(char for char in str(key).casefold() if char.isalnum()) not in _REDACTED_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_safe_snapshot(item) for item in value]
    return value


async def record_event(
    session: AsyncSession,
    *,
    actor_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request_id: str,
) -> AuditEvent:
    """Add an audit event to the caller's transaction; this function never commits."""
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=_safe_snapshot(before),
        after=_safe_snapshot(after),
        request_id=request_id[:64],
    )
    session.add(event)
    await session.flush()
    return event
