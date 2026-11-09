"""API client creation and lookup; callers own transaction boundaries."""

from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.security import generate_api_key, hash_api_key, verify_api_key
from aprkb.modules.audit.service import record_event
from aprkb.modules.identity.models import ApiClient, StaffSession
from aprkb.seeds.load import run_seed

VALID_ROLES = {"admin", "curator", "reviewer", "client"}
ADMIN_LIFECYCLE_LOCK_ID = 280627590466
LOCAL_DEMO_LOCK_ID = ADMIN_LIFECYCLE_LOCK_ID + 1


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
    if plaintext.startswith(("staff_", "google_", "email_")):
        result = await session.scalar(
            select(ApiClient)
            .join(StaffSession, StaffSession.client_id == ApiClient.id)
            .where(
                StaffSession.token_hash == hash_api_key(plaintext),
                StaffSession.expires_at > datetime.now(UTC),
                ApiClient.is_active.is_(True),
            )
        )
        return result
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


async def initialize_local_demo_session(
    session: AsyncSession, *, request_id: str
) -> tuple[ApiClient, str]:
    """Seed local demo data and rotate the active development curator key."""
    try:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": LOCAL_DEMO_LOCK_ID}
        )
        previous_keys = await session.scalars(
            select(ApiClient)
            .where(
                ApiClient.name == "Local Demo Curator",
                ApiClient.role == "curator",
                ApiClient.is_active.is_(True),
            )
            .with_for_update()
        )
        for previous_key in previous_keys:
            previous_key.is_active = False

        await run_seed(session)
        client, plaintext = await create_api_key(session, name="Local Demo Curator", role="curator")
        await record_event(
            session,
            actor_id=None,
            action="local_demo.session.create",
            entity_type="api_client",
            entity_id=client.id,
            after={"name": client.name, "role": client.role},
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return client, plaintext


def hash_password(password: str, salt: str | None = None) -> str:
    import hashlib
    import secrets

    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    import hmac

    return hmac.compare_digest(hash_password(password, stored.split("$", 1)[0]), stored)
