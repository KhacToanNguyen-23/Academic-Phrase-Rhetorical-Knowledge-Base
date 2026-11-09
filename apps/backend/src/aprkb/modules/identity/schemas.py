"""HTTP schemas for admin-managed API clients."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: Literal["admin", "curator", "reviewer", "client"]


class ApiKeyCreated(BaseModel):
    id: UUID
    name: str
    role: str
    key_prefix: str
    api_key: str


class ApiKeySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    role: str
    key_prefix: str
    is_active: bool


class ApiKeyRevoked(BaseModel):
    id: UUID
    is_active: bool


class AuthenticatedClient(BaseModel):
    id: UUID
    name: str
    role: str


class DemoSession(AuthenticatedClient):
    api_key: str


class EmailAddress(BaseModel):
    email: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def organization_email(cls, value: str) -> str:
        import re

        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@hyperdatalab\.org", value):
            raise ValueError("Use an @hyperdatalab.org email address")
        return value


class EmailLogin(EmailAddress):
    password: str = Field(min_length=8, max_length=128, repr=False)


class GoogleLogin(BaseModel):
    credential: str = Field(min_length=1, max_length=8192, repr=False)


class GoogleConfig(BaseModel):
    client_id: str | None
    nonce: str
