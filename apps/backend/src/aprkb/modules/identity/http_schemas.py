"""HTTP schemas for admin-managed API clients."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
