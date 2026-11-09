from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.identity import google
from aprkb.modules.identity.service import authenticate_api_key, create_api_key


async def test_google_sessions_and_one_time_admin_binding(postgres_test_engine, monkeypatch):
    token = dict(
        sub="staff-subject",
        email="staff@hyperdatalab.org",
        hd="hyperdatalab.org",
        email_verified=True,
        nonce="nonce",
    )
    monkeypatch.setattr(
        google, "verify_google_credential", MagicMock(side_effect=lambda *args: token)
    )
    async with AsyncSession(postgres_test_engine, expire_on_commit=False) as session:
        result = await google.google_session(
            session, credential="token", client_id="id", nonce="nonce"
        )
        assert result.role == "curator"
        client = await authenticate_api_key(session, result.api_key)
        assert client.google_subject == "staff-subject"
        again = await google.google_session(
            session, credential="token", client_id="id", nonce="nonce"
        )
        assert again.id == result.id
        client.is_active = False
        await session.commit()
        assert await authenticate_api_key(session, result.api_key) is None
        with pytest.raises(HTTPException) as disabled:
            await google.google_session(session, credential="token", client_id="id", nonce="nonce")
        assert disabled.value.status_code == 403
        await session.rollback()
        admin, key = await create_api_key(session, name="Admin setup test", role="admin")
        await session.commit()
        admin_id = admin.id
        token = dict(token, sub="admin-subject", email="admin@hyperdatalab.org")
        result = await google.google_session(
            session,
            credential="token",
            client_id="id",
            nonce="nonce",
            setup_key=key,
        )
        assert result.id == admin_id
        assert result.role == "admin"
        with pytest.raises(HTTPException) as repeated:
            await google.google_session(
                session,
                credential="token",
                client_id="id",
                nonce="nonce",
                setup_key=key,
            )
        assert repeated.value.status_code == 403
