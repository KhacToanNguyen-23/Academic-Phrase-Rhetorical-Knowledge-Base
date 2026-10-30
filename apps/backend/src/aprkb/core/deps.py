"""Shared request dependencies for database access and API authentication."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.identity.models import ApiClient
from aprkb.modules.identity.service import authenticate_api_key


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()


async def get_current_client(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiClient:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    client = await authenticate_api_key(session, x_api_key)
    if client is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return client
