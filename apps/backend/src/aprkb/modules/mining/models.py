"""SQLAlchemy persistence models for the mining domain."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, MutableEntityMixin


class Candidate(MutableEntityMixin, Base):
    __tablename__ = "candidates"
    canonical_frame: Mapped[str] = mapped_column(Text)
    slots: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    intent_id: Mapped[UUID | None] = mapped_column(ForeignKey("intents.id"))
    confidence: Mapped[float | None] = mapped_column(Float)
    epistemic_strength: Mapped[str | None] = mapped_column(String(32))
    source_sentence_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid(as_uuid=True)), default=list)
    cluster_key: Mapped[str | None] = mapped_column(String(255))
    matched_pattern_id: Mapped[UUID | None] = mapped_column(ForeignKey("phrase_patterns.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")


class Job(MutableEntityMixin, Base):
    __tablename__ = "jobs"
    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
