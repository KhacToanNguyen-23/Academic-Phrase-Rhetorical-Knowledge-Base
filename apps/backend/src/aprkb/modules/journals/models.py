"""SQLAlchemy persistence models for the journals domain."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, EntityMixin, MutableEntityMixin


class JournalProfile(MutableEntityMixin, Base):
    __tablename__ = "journal_profiles"
    name: Mapped[str] = mapped_column(String(255))
    issn: Mapped[str | None] = mapped_column(String(16), unique=True)
    publisher: Mapped[str | None] = mapped_column(String(255))
    field: Mapped[str | None] = mapped_column(String(255))
    subfield: Mapped[str | None] = mapped_column(String(255))
    similar_journal_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid(as_uuid=True)), default=list)


class GuidelineRule(EntityMixin, Base):
    __tablename__ = "guideline_rules"
    journal_id: Mapped[UUID] = mapped_column(ForeignKey("journal_profiles.id"))
    rule_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    active_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JournalFingerprint(EntityMixin, Base):
    __tablename__ = "journal_fingerprints"
    journal_id: Mapped[UUID] = mapped_column(ForeignKey("journal_profiles.id"))
    genre_id: Mapped[UUID] = mapped_column(ForeignKey("article_genres.id"))
    # Technical placeholder dimension; fingerprint computation remains out of scope.
    vector: Mapped[list[float]] = mapped_column(Vector(384))
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
