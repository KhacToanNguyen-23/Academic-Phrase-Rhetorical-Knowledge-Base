from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from aprkb.core.security import hash_api_key
from aprkb.modules.identity.router import email_login, register_email, setup_email
from aprkb.modules.identity.schemas import EmailLogin
from aprkb.modules.identity.service import authenticate_api_key, hash_password, verify_password

PASSWORD = "long-password"
ADMIN_EMAIL = "admin@hyperdatalab.org"
NEW_EMAIL = "new@hyperdatalab.org"


def credentials(email: str = ADMIN_EMAIL, password: str = PASSWORD) -> EmailLogin:
    return EmailLogin(email=email, password=password)


def test_email_domain_and_password_validation():
    assert credentials(" Admin@HyperDataLab.org ").email == ADMIN_EMAIL
    for email in [
        "a@gmail.com",
        "a@hyperdatalab.org.evil.com",
        "a@@hyperdatalab.org",
        "@hyperdatalab.org",
    ]:
        with pytest.raises(ValidationError):
            credentials(email)
    with pytest.raises(ValidationError):
        credentials(password="short")


def test_password_is_salted_and_verified():
    first = hash_password(PASSWORD)
    assert first != hash_password(PASSWORD)
    assert verify_password(PASSWORD, first)
    assert not verify_password("wrong-password", first)


async def test_setup_cannot_overwrite_existing_account():
    client = SimpleNamespace(id=uuid4(), role="admin", email=ADMIN_EMAIL)
    session = AsyncMock()
    session.scalar.return_value = client
    with pytest.raises(HTTPException) as error:
        await setup_email(credentials(), client, session)
    assert error.value.status_code == 409
    session.commit.assert_not_called()


async def test_first_setup_binds_email_and_hashes_password():
    client = SimpleNamespace(id=uuid4(), name="Admin", role="admin", email=None)
    session = AsyncMock()
    session.scalar.return_value = client
    await setup_email(credentials(), client, session)
    assert client.email == ADMIN_EMAIL
    assert verify_password(PASSWORD, client.password_hash)
    session.commit.assert_awaited_once()


@pytest.mark.parametrize(
    "account",
    [
        None,
        SimpleNamespace(password_hash=None, is_active=True, role="curator"),
        SimpleNamespace(
            password_hash=hash_password("other-password"), is_active=True, role="admin"
        ),
        SimpleNamespace(password_hash=hash_password(PASSWORD), is_active=False, role="admin"),
    ],
    ids=["unregistered", "no-password", "wrong-password", "disabled"],
)
async def test_login_rejected(account):
    session = AsyncMock()
    session.scalar.return_value = account
    with pytest.raises(HTTPException) as error:
        await email_login(credentials(), session)
    assert error.value.status_code == 401
    session.commit.assert_not_called()


async def test_session_authentication_checks_expiry_and_active_account():
    session = AsyncMock()
    session.scalar.return_value = None
    assert await authenticate_api_key(session, "staff_expired") is None
    query = str(session.scalar.call_args.args[0])
    assert "staff_sessions.expires_at >" in query
    assert "api_clients.is_active IS true" in query


async def test_successful_login_issues_hashed_expiring_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.return_value = SimpleNamespace(
        id=uuid4(),
        name="Admin",
        role="admin",
        is_active=True,
        password_hash=hash_password(PASSWORD),
    )
    result = await email_login(credentials(), session)
    stored = session.add.call_args.args[0]
    assert stored.token_hash == hash_api_key(result.api_key)
    assert stored.token_hash != result.api_key
    assert 28_790 < (stored.expires_at - datetime.now(UTC)).total_seconds() <= 28_800
    session.commit.assert_awaited_once()


async def test_registration_hashes_password_and_does_not_issue_session():
    session = AsyncMock()
    session.scalar.return_value = None
    client = SimpleNamespace(id=uuid4(), name="New", role="curator", email=None)
    with patch(
        "aprkb.modules.identity.router.create_api_key", AsyncMock(return_value=(client, "unused"))
    ):
        result = await register_email(credentials(NEW_EMAIL), session)
    assert client.email == NEW_EMAIL
    assert verify_password(PASSWORD, client.password_hash)
    assert not hasattr(result, "api_key")
    session.commit.assert_awaited_once()


async def test_legacy_curator_can_set_password_by_registering():
    session = AsyncMock()
    client = SimpleNamespace(
        id=uuid4(), name="Old", role="curator", password_hash=None, google_subject=None
    )
    session.scalar.return_value = client
    await register_email(credentials(NEW_EMAIL), session)
    assert verify_password(PASSWORD, client.password_hash)
    session.commit.assert_awaited_once()


@pytest.mark.parametrize(
    "account",
    [
        SimpleNamespace(role="admin", password_hash=None, google_subject=None),
        SimpleNamespace(role="curator", password_hash="salt$hash", google_subject=None),
        SimpleNamespace(role="curator", password_hash=None, google_subject="google-id"),
    ],
    ids=["admin", "has-password", "google"],
)
async def test_registration_cannot_overwrite_account(account):
    session = AsyncMock()
    session.scalar.return_value = account
    with pytest.raises(HTTPException) as error:
        await register_email(credentials(), session)
    assert error.value.status_code == 409
    session.commit.assert_not_called()
