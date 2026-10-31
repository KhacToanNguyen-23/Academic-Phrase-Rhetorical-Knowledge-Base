"""API key hashing and role checks (NFR-04)."""

import hashlib
import hmac
import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException

from aprkb.modules.identity.models import ApiClient

ROLE_ORDER = {"client": 0, "reviewer": 1, "curator": 2, "admin": 3}


def hash_api_key(plaintext: str) -> str:
    """Hash a high-entropy API key before it is stored."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def verify_api_key(plaintext: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_api_key(plaintext), hashed)


def generate_api_key() -> str:
    return f"aprkb_{secrets.token_urlsafe(32)}"


def role_allows(actor_role: str, required_role: str) -> bool:
    actor_level = ROLE_ORDER.get(actor_role)
    required_level = ROLE_ORDER.get(required_role)
    return actor_level is not None and required_level is not None and actor_level >= required_level


def require_role(
    required_role: str,
) -> Callable[..., Awaitable[ApiClient]]:
    """Return a FastAPI dependency enforcing the PRD role hierarchy."""
    if required_role not in ROLE_ORDER:
        raise ValueError(f"Unknown required role: {required_role}")

    from aprkb.core.deps import get_current_client

    async def dependency(
        client: Annotated[ApiClient, Depends(get_current_client)],
    ) -> ApiClient:
        if not role_allows(client.role, required_role):
            raise HTTPException(status_code=403, detail="Insufficient role")
        return client

    return dependency
