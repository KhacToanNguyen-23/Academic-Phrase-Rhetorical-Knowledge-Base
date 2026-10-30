"""SQLAlchemy persistence models for the recommendation domain."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, EntityMixin


class Feedback(EntityMixin, Base):
    __tablename__ = "feedback"
    client_id: Mapped[UUID] = mapped_column(ForeignKey("api_clients.id"))
    recommendation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True))
    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    signal: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Override(EntityMixin, Base):
    __tablename__ = "overrides"
    client_id: Mapped[UUID] = mapped_column(ForeignKey("api_clients.id"))
    validation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True))
    rule_code: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)


class RecommendationLog(EntityMixin, Base):
    __tablename__ = "recommendation_logs"
    request: Mapped[dict[str, Any]] = mapped_column(JSONB)
    results: Mapped[dict[str, Any]] = mapped_column(JSONB)
    policy_versions: Mapped[dict[str, Any]] = mapped_column(JSONB)
