"""SQLAlchemy persistence models for the identity domain."""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, MutableEntityMixin


class ApiClient(MutableEntityMixin, Base):
    __tablename__ = "api_clients"
    name: Mapped[str] = mapped_column(String(255))
    key_hash: Mapped[str] = mapped_column(String(255), unique=True)
    key_prefix: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
