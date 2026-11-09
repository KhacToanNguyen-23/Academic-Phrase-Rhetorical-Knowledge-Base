"""SQLAlchemy persistence models for the identity domain."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, MutableEntityMixin


class ApiClient(MutableEntityMixin, Base):
    __tablename__ = "api_clients"
    name: Mapped[str] = mapped_column(String(255))
    key_hash: Mapped[str] = mapped_column(String(255), unique=True)
    key_prefix: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    google_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))


class StaffSession(MutableEntityMixin, Base):
    __tablename__ = "staff_sessions"
    client_id: Mapped[UUID] = mapped_column(ForeignKey("api_clients.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
