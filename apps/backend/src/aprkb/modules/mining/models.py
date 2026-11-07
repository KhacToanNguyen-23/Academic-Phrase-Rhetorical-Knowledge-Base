"""SQLAlchemy persistence models for the mining domain."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
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
    occurrences: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    matched_pattern_id: Mapped[UUID | None] = mapped_column(ForeignKey("phrase_patterns.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")


class Job(MutableEntityMixin, Base):
    __tablename__ = "jobs"
    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=4, server_default="4")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lock_token: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    manual_retries: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    progress_stage: Mapped[str | None] = mapped_column(String(64))
    progress_completed: Mapped[int | None] = mapped_column(Integer)
    progress_total: Mapped[int | None] = mapped_column(Integer)


class JobAttempt(MutableEntityMixin, Base):
    __tablename__ = "job_attempts"
    __table_args__ = (UniqueConstraint("job_id", "attempt_no", name="uq_job_attempt_number"),)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(16), default="processing")
    stage: Mapped[str | None] = mapped_column(String(64))
    completed: Mapped[int | None] = mapped_column(Integer)
    total: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobAlert(MutableEntityMixin, Base):
    __tablename__ = "job_alerts"
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"), unique=True)
    failure_count: Mapped[int] = mapped_column(Integer)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[UUID | None] = mapped_column(ForeignKey("api_clients.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
