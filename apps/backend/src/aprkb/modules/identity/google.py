"""Google token verification and one-time admin binding."""

import secrets
from asyncio import to_thread
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.id_token import verify_oauth2_token
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.security import hash_api_key
from aprkb.modules.identity.models import ApiClient, StaffSession
from aprkb.modules.identity.schemas import DemoSession
from aprkb.modules.identity.service import authenticate_api_key, create_api_key


def verify_google_credential(credential: str, client_id: str, nonce: str) -> dict:
    try:
        claims = verify_oauth2_token(credential, GoogleRequest(), audience=client_id)
    except (ValueError, GoogleAuthError):
        raise HTTPException(
            status_code=401, detail="Google sign-in could not be verified"
        ) from None
    email = claims.get("email", "").lower()
    if claims.get("email_verified") is not True or email.count("@") != 1 or not claims.get("sub"):
        raise HTTPException(status_code=403, detail="Use a Google account with a verified email")
    if not nonce or not secrets.compare_digest(claims.get("nonce", ""), nonce):
        raise HTTPException(status_code=401, detail="Sign-in expired. Reload and try again")
    return claims


async def google_session(
    session: AsyncSession,
    *,
    credential: str,
    client_id: str,
    nonce: str,
    setup_key: str | None = None,
) -> DemoSession:
    claims = await to_thread(verify_google_credential, credential, client_id, nonce)
    email, subject = claims["email"].lower(), claims["sub"]
    await session.execute(text("SELECT pg_advisory_xact_lock(280627590469)"))
    client = await session.scalar(select(ApiClient).where(ApiClient.google_subject == subject))
    if setup_key:
        target = await authenticate_api_key(session, setup_key)
        if target is None or target.role != "admin" or target.google_subject is not None:
            raise HTTPException(
                status_code=403, detail="Admin setup key is invalid or already configured"
            )
        if client is not None or target.email not in {None, email}:
            raise HTTPException(status_code=409, detail="Account is already configured")
        existing = await session.scalar(select(ApiClient).where(ApiClient.email == email))
        if existing is not None and existing.id != target.id:
            raise HTTPException(status_code=409, detail="Email is already configured")
        client = target
        client.email, client.google_subject = email, subject
    elif client is None:
        existing = await session.scalar(select(ApiClient).where(ApiClient.email == email))
        if existing is not None:
            if existing.role == "admin" or existing.google_subject or not existing.is_active:
                raise HTTPException(
                    status_code=409,
                    detail="Existing account requires administrator-assisted Google setup",
                )
            client = existing
            client.google_subject = subject
        else:
            client, _ = await create_api_key(
                session, name=claims.get("name", email)[:255], role="curator"
            )
            client.email, client.google_subject = email, subject
    if not client.is_active or client.role not in {"admin", "curator"}:
        raise HTTPException(status_code=403, detail="Staff account is disabled or has no access")
    token = "google_" + secrets.token_urlsafe(32)
    session.add(
        StaffSession(
            client_id=client.id,
            token_hash=hash_api_key(token),
            expires_at=datetime.now(UTC) + timedelta(hours=8),
        )
    )
    await session.commit()
    return DemoSession(id=client.id, name=client.name, role=client.role, api_key=token)
