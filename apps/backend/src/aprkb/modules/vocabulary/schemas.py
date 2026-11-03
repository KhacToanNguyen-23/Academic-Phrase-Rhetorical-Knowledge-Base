"""Pydantic contracts for vocabulary imports."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ImportResult(BaseModel):
    run_id: UUID
    source_kind: str
    rows_read: int
    inserted: int
    updated: int
    skipped: int
    warnings: list[str]


class ImportRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_kind: str
    filename: str
    sha256: str
    rows_read: int
    inserted: int
    updated: int
    skipped: int
    warnings: list[Any]
    created_at: datetime


class ImportRunPage(BaseModel):
    items: list[ImportRunRead]
    total: int
