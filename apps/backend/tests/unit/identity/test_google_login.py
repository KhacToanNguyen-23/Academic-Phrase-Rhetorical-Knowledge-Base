from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from aprkb.modules.identity import google


def claims(**changes):
    return dict(
        sub="google-subject",
        email="staff@hyperdatalab.org",
        hd="hyperdatalab.org",
        email_verified=True,
        nonce="nonce",
        **changes,
    )


def test_google_verifier_checks_audience_and_nonce(monkeypatch):
    verify = MagicMock(return_value=claims())
    monkeypatch.setattr(google, "verify_oauth2_token", verify)
    assert google.verify_google_credential("signed-token", "client-id", "nonce")["sub"]
    assert verify.call_args.kwargs["audience"] == "client-id"
    with pytest.raises(HTTPException) as error:
        google.verify_google_credential("signed-token", "client-id", "wrong-nonce")
    assert error.value.status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "staff@gmail.com", "hd": None},
        {"email": "staff@example.edu", "hd": "example.edu"},
    ],
)
def test_google_accepts_any_domain(monkeypatch, changes):
    token = claims()
    token.update(changes)
    monkeypatch.setattr(google, "verify_oauth2_token", MagicMock(return_value=token))
    assert google.verify_google_credential("token", "client-id", "nonce") == token


@pytest.mark.parametrize(
    "changes",
    [
        {"email_verified": False},
        {"sub": ""},
        {"email": ""},
        {"email": "a@@gmail.com"},
    ],
)
def test_google_requires_verified_account(monkeypatch, changes):
    token = claims()
    token.update(changes)
    monkeypatch.setattr(google, "verify_oauth2_token", MagicMock(return_value=token))
    with pytest.raises(HTTPException) as error:
        google.verify_google_credential("token", "client-id", "nonce")
    assert error.value.status_code == 403


def test_invalid_signature_or_expired_token_rejected(monkeypatch):
    monkeypatch.setattr(google, "verify_oauth2_token", MagicMock(side_effect=ValueError))
    with pytest.raises(HTTPException) as error:
        google.verify_google_credential("fake-token", "client-id", "nonce")
    assert error.value.status_code == 401


async def test_google_login_preserves_role_and_creates_session(monkeypatch):
    monkeypatch.setattr(google, "verify_google_credential", MagicMock(return_value=claims()))
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.return_value = SimpleNamespace(
        id=uuid4(), name="Admin", role="admin", is_active=True
    )
    result = await google.google_session(session, credential="token", client_id="id", nonce="nonce")
    assert result.role == "admin"
    assert result.api_key.startswith("google_")
    assert session.add.call_args.args[0].token_hash != result.api_key
    session.commit.assert_awaited_once()


async def test_google_cannot_claim_existing_email(monkeypatch):
    monkeypatch.setattr(google, "verify_google_credential", MagicMock(return_value=claims()))
    session = AsyncMock()
    session.scalar.side_effect = [None, SimpleNamespace(role="admin")]
    with pytest.raises(HTTPException) as error:
        await google.google_session(session, credential="token", client_id="id", nonce="nonce")
    assert error.value.status_code == 409
    session.commit.assert_not_called()


async def test_admin_key_binding_is_one_time(monkeypatch):
    monkeypatch.setattr(google, "verify_google_credential", MagicMock(return_value=claims()))
    monkeypatch.setattr(
        google,
        "authenticate_api_key",
        AsyncMock(
            return_value=SimpleNamespace(
                role="admin",
                google_subject="already-bound",
            )
        ),
    )
    session = AsyncMock()
    session.scalar.return_value = None
    with pytest.raises(HTTPException) as error:
        await google.google_session(
            session, credential="token", client_id="id", nonce="nonce", setup_key="key"
        )
    assert error.value.status_code == 403
    session.commit.assert_not_called()


async def test_google_web_identity_rejects_api_key_and_legacy_session():
    from starlette.requests import Request

    from aprkb.modules.identity.router import google_identity

    client = SimpleNamespace(id=uuid4(), name="Admin", role="admin", google_subject="subject")
    for token in ["aprkb_demo-key", "staff_password-session"]:
        request = Request({"type": "http", "headers": [(b"x-api-key", token.encode())]})
        with pytest.raises(HTTPException) as error:
            await google_identity(request, client)
        assert error.value.status_code == 401
    request = Request({"type": "http", "headers": [(b"x-api-key", b"google_verified-session")]})
    assert (await google_identity(request, client)).id == client.id


async def test_web_session_restricts_domain_only_for_email_login():
    from starlette.requests import Request

    from aprkb.modules.identity.router import web_identity

    def request(token: bytes) -> Request:
        return Request({"type": "http", "headers": [(b"x-api-key", token)]})

    client = SimpleNamespace(
        id=uuid4(), name="Staff", role="curator", email="a@gmail.com", google_subject="subject"
    )
    assert (await web_identity(request(b"google_session"), client)).id == client.id
    with pytest.raises(HTTPException) as error:
        await web_identity(request(b"email_session"), client)
    assert error.value.status_code == 401


async def test_local_request_without_credentials_is_rejected():
    from starlette.requests import Request

    from aprkb.core.deps import get_current_client

    request = Request({"type": "http", "client": ("127.0.0.1", 1234), "path": "/v1/patterns"})
    session = AsyncMock()
    with pytest.raises(HTTPException) as error:
        await get_current_client(request, session, None)
    assert error.value.status_code == 401
    session.scalar.assert_not_called()
