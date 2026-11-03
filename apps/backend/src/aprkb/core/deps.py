"""Shared request dependencies for database access and API authentication."""

from collections.abc import AsyncIterator
from ipaddress import ip_address
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.identity.models import ApiClient
from aprkb.modules.identity.service import authenticate_api_key, create_api_key


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()


async def get_current_client(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiClient:
    if not x_api_key:
        host = request.client.host if request.client else ""
        try:
            loopback = ip_address(host).is_loopback
        except ValueError:
            loopback = False
        demo_client_id = getattr(request.app.state, "local_demo_client_id", None)
        # Local UI demo convenience only. Other environments/hosts require
        # a client key (NFR-04).
        if (
            request.app.state.settings.app_env == "local"
            and loopback
            and request.url.path != "/v1/auth/me"
        ):
            client = await session.get(ApiClient, demo_client_id) if demo_client_id else None
            if client is None or not client.is_active or client.role != "client":
                async with request.app.state.local_demo_lock:
                    demo_client_id = request.app.state.local_demo_client_id
                    client = (
                        await session.get(ApiClient, demo_client_id) if demo_client_id else None
                    )
                    if client is None or not client.is_active or client.role != "client":
                        client = await session.scalar(
                            select(ApiClient).where(
                                ApiClient.name == "Local Writer Demo",
                                ApiClient.role == "client",
                                ApiClient.is_active.is_(True),
                            )
                        )
                        if client is None:
                            client, _ = await create_api_key(
                                session, name="Local Writer Demo", role="client"
                            )
                            await session.commit()
                        request.app.state.local_demo_client_id = client.id
            if client is not None and client.is_active and client.role == "client":
                return client
        raise HTTPException(status_code=401, detail="API key required")
    client = await authenticate_api_key(session, x_api_key)
    if client is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return client
