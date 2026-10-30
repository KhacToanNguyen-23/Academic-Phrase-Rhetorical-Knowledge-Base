"""API client creation and lookup; callers own transaction boundaries."""

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.security import generate_api_key, hash_api_key, verify_api_key
from aprkb.modules.identity.models import ApiClient

VALID_ROLES = {"admin", "curator", "reviewer", "client"}
ADMIN_LIFECYCLE_LOCK_ID = 280627590466


async def create_api_key(session: AsyncSession, *, name: str, role: str) -> tuple[ApiClient, str]:
    if role not in VALID_ROLES:
        raise ValueError(f"Unknown API client role: {role}")
    plaintext = generate_api_key()
    client = ApiClient(
        name=name,
        key_hash=hash_api_key(plaintext),
        key_prefix=plaintext[:12],
        role=role,
        is_active=True,
    )
    session.add(client)
    await session.flush()
    return client, plaintext


async def authenticate_api_key(session: AsyncSession, plaintext: str) -> ApiClient | None:
    if not plaintext:
        return None
    key_hash = hash_api_key(plaintext)
    client = await session.scalar(select(ApiClient).where(ApiClient.key_hash == key_hash))
    if client is None or not client.is_active or not verify_api_key(plaintext, client.key_hash):
        return None
    return client


async def bootstrap_admin(
    session: AsyncSession, *, name: str = "Bootstrap admin"
) -> tuple[ApiClient, str]:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": ADMIN_LIFECYCLE_LOCK_ID},
    )
    admin_count = await session.scalar(
        select(func.count())
        .select_from(ApiClient)
        .where(ApiClient.role == "admin", ApiClient.is_active.is_(True))
    )
    if admin_count:
        raise RuntimeError("An admin API key already exists")
    return await create_api_key(session, name=name, role="admin")
