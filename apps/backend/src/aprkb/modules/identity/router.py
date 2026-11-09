"""Identity and admin API-key HTTP endpoints."""

import secrets
from asyncio import to_thread
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_current_client, get_db_session
from aprkb.core.security import require_role
from aprkb.modules.audit.service import record_event
from aprkb.modules.identity.models import ApiClient, StaffSession
from aprkb.modules.identity.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyRevoked,
    ApiKeySummary,
    AuthenticatedClient,
    DemoSession,
    EmailLogin,
    GoogleConfig,
    GoogleLogin,
)
from aprkb.modules.identity.service import (
    ADMIN_LIFECYCLE_LOCK_ID,
    create_api_key,
    hash_password,
    verify_password,
)

router = APIRouter(tags=["identity"])
admin_router = APIRouter(tags=["admin api keys"])

AdminClient = Annotated[ApiClient, Depends(require_role("admin"))]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Authenticated = Annotated[ApiClient, Depends(get_current_client)]


@router.get("/me", response_model=AuthenticatedClient)
async def current_identity(client: Authenticated) -> AuthenticatedClient:
    return AuthenticatedClient(id=client.id, name=client.name, role=client.role)


@admin_router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_key(
    payload: ApiKeyCreate,
    request: Request,
    client: AdminClient,
    session: DatabaseSession,
) -> ApiKeyCreated:
    try:
        created, plaintext = await create_api_key(session, name=payload.name, role=payload.role)
        await record_event(
            session,
            actor_id=client.id,
            action="api_key.create",
            entity_type="api_client",
            entity_id=created.id,
            after={"id": str(created.id), "name": created.name, "role": created.role},
            request_id=request.state.request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return ApiKeyCreated(
        id=created.id,
        name=created.name,
        role=created.role,
        key_prefix=created.key_prefix,
        api_key=plaintext,
    )


@admin_router.get("/api-keys", response_model=list[ApiKeySummary])
async def list_keys(
    _client: AdminClient,
    session: DatabaseSession,
) -> list[ApiKeySummary]:
    clients = await session.scalars(select(ApiClient).order_by(ApiClient.created_at, ApiClient.id))
    return [
        ApiKeySummary(
            id=client.id,
            name=client.name,
            role=client.role,
            key_prefix=client.key_prefix,
            is_active=client.is_active,
        )
        for client in clients
    ]


@admin_router.delete("/api-keys", response_model=ApiKeyRevoked)
async def revoke_key(
    client_id: Annotated[UUID, Query()],
    request: Request,
    actor: AdminClient,
    session: DatabaseSession,
) -> ApiKeyRevoked:
    client = await session.get(ApiClient, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="API client not found")
    if client.role == "admin" and client.is_active:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": ADMIN_LIFECYCLE_LOCK_ID},
        )
        active_admins = await session.scalar(
            select(func.count())
            .select_from(ApiClient)
            .where(ApiClient.role == "admin", ApiClient.is_active.is_(True))
        )
        if active_admins is not None and active_admins <= 1:
            raise HTTPException(
                status_code=409,
                detail="Cannot revoke the last active admin API key",
            )
    before = {"is_active": client.is_active}
    client.is_active = False
    try:
        await record_event(
            session,
            actor_id=actor.id,
            action="api_key.revoke",
            entity_type="api_client",
            entity_id=client.id,
            before=before,
            after={"is_active": False},
            request_id=request.state.request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return ApiKeyRevoked(id=client.id, is_active=client.is_active)


@router.post("/setup", response_model=AuthenticatedClient)
async def setup_email(
    payload: EmailLogin,
    client: Authenticated,
    session: DatabaseSession,
) -> AuthenticatedClient:
    if client.role not in {"admin", "curator"}:
        raise HTTPException(status_code=403, detail="Staff access required")
    locked = await session.scalar(
        select(ApiClient)
        .where(ApiClient.id == client.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked is None:
        raise HTTPException(status_code=401, detail="Account unavailable")
    if locked.email is not None:
        raise HTTPException(
            status_code=409, detail="This key is already linked to an email. Please sign in"
        )
    locked.email = payload.email
    locked.password_hash = await to_thread(hash_password, payload.password)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Email is already registered to another account"
        ) from None
    return AuthenticatedClient(id=client.id, name=client.name, role=client.role)


@router.post("/login", response_model=DemoSession)
async def email_login(payload: EmailLogin, session: DatabaseSession) -> DemoSession:
    from aprkb.core.security import hash_api_key

    client = await session.scalar(select(ApiClient).where(ApiClient.email == payload.email))
    stored = client.password_hash if client and client.password_hash else DUMMY_PASSWORD_HASH
    valid = await to_thread(verify_password, payload.password, stored)
    if (
        client is None
        or not client.password_hash
        or not valid
        or not client.is_active
        or client.role not in {"admin", "curator"}
    ):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = "email_" + secrets.token_urlsafe(32)
    session.add(
        StaffSession(
            client_id=client.id,
            token_hash=hash_api_key(token),
            expires_at=datetime.now(UTC) + timedelta(hours=8),
        )
    )
    await session.commit()
    return DemoSession(id=client.id, name=client.name, role=client.role, api_key=token)


DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


@router.post("/logout", status_code=204)
async def logout(request: Request, client: Authenticated, session: DatabaseSession) -> None:
    from aprkb.core.security import hash_api_key

    token = request.headers.get("X-API-Key", "")
    await session.execute(
        delete(StaffSession).where(
            StaffSession.client_id == client.id,
            StaffSession.token_hash == hash_api_key(token),
        )
    )
    await session.commit()


@router.get("/google/config", response_model=GoogleConfig)
async def google_config(request: Request, response: Response) -> GoogleConfig:
    nonce = secrets.token_urlsafe(32)
    response.set_cookie(
        "aprkb-google-nonce",
        nonce,
        max_age=600,
        httponly=True,
        samesite="strict",
        secure=request.app.state.settings.app_env not in {"local", "test"},
        path="/v1/auth/google",
    )
    response.headers["Cache-Control"] = "no-store"
    return GoogleConfig(client_id=request.app.state.settings.google_client_id or None, nonce=nonce)


@router.post("/google", response_model=DemoSession)
async def google_login(
    payload: GoogleLogin,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> DemoSession:
    from aprkb.modules.identity.google import google_session

    client_id = request.app.state.settings.google_client_id
    if not client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    nonce = request.cookies.get("aprkb-google-nonce", "")
    if not nonce:
        raise HTTPException(status_code=401, detail="Sign-in expired. Reload and try again")
    result = await google_session(
        session,
        credential=payload.credential,
        client_id=client_id,
        nonce=nonce,
        setup_key=request.headers.get("X-API-Key"),
    )
    response.delete_cookie("aprkb-google-nonce", path="/v1/auth/google")
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/google/me", response_model=AuthenticatedClient)
async def google_identity(request: Request, client: Authenticated) -> AuthenticatedClient:
    if not request.headers.get("X-API-Key", "").startswith("google_") or not client.google_subject:
        raise HTTPException(status_code=401, detail="Google sign-in required")
    return AuthenticatedClient(id=client.id, name=client.name, role=client.role)


@router.post("/register", status_code=201, response_model=AuthenticatedClient)
async def register_email(payload: EmailLogin, session: DatabaseSession) -> AuthenticatedClient:
    await session.execute(text("SELECT pg_advisory_xact_lock(280627590469)"))
    existing = await session.scalar(select(ApiClient).where(ApiClient.email == payload.email))
    # Curators registered before passwords existed set theirs by registering again.
    legacy = (
        existing is not None
        and existing.role == "curator"
        and not existing.password_hash
        and not existing.google_subject
    )
    if existing is not None and not legacy:
        raise HTTPException(status_code=409, detail="Email is already registered. Please sign in")
    if existing is not None:
        client = existing
    else:
        client, _ = await create_api_key(session, name=payload.email, role="curator")
        client.email = payload.email
    client.password_hash = await to_thread(hash_password, payload.password)
    await session.commit()
    # Registration never creates or returns a browser session.
    return AuthenticatedClient(id=client.id, name=client.name, role=client.role)


@router.get("/session/me", response_model=AuthenticatedClient)
async def web_identity(request: Request, client: Authenticated) -> AuthenticatedClient:
    token = request.headers.get("X-API-Key", "")
    google = token.startswith("google_") and bool(client.google_subject)
    email = (
        token.startswith("email_")
        and bool(client.email)
        and client.email.endswith("@hyperdatalab.org")
    )
    if not (google or email):
        raise HTTPException(status_code=401, detail="Sign in with Google or organization email")
    if client.role not in {"admin", "curator"}:
        raise HTTPException(status_code=403, detail="Staff access required")
    return AuthenticatedClient(id=client.id, name=client.name, role=client.role)
