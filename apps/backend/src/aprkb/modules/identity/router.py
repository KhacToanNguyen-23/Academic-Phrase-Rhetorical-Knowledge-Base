"""Identity and admin API-key HTTP endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.audit.service import record_event
from aprkb.modules.identity.http_schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyRevoked,
    ApiKeySummary,
)
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.identity.service import ADMIN_LIFECYCLE_LOCK_ID, create_api_key

router = APIRouter(tags=["identity"])
admin_router = APIRouter(tags=["admin api keys"])

AdminClient = Annotated[ApiClient, Depends(require_role("admin"))]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


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
