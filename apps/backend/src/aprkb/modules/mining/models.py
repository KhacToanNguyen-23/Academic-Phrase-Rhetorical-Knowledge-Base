"""SQLAlchemy persistence models for the mining domain."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, MutableEntityMixin


class Candidate(MutableEntityMixin, Base):
    __tablename__ = "candidates"
    # One candidate per cluster: new sources are appended to it (see the worker repository).
    __table_args__ = (UniqueConstraint("cluster_key", name="uq_candidates_cluster_key"),)
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


class CandidateLabel(MutableEntityMixin, Base):
    """Proposed or human-confirmed frame label values, without source sentence text."""

    __tablename__ = "candidate_labels"
    __table_args__ = (
        UniqueConstraint("candidate_id", "label_code", name="uq_candidate_labels_candidate_code"),
        CheckConstraint(
            "status IN ('proposed', 'confirmed', 'rejected')", name="ck_candidate_labels_status"
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_candidate_labels_confidence",
        ),
    )
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    label_code: Mapped[str] = mapped_column(String(64))
    value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    source: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    options: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    evidence: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    needs_attention: Mapped[bool] = mapped_column(Boolean, default=False)
    agreement: Mapped[str | None] = mapped_column(String(32), nullable=True)
    proposed_by_run: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("api_clients.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EpistemicLexiconEntry(MutableEntityMixin, Base):
    """Versioned lexical assessment with no source-sentence payload."""

    __tablename__ = "epistemic_lexicon_entries"
    __table_args__ = (
        UniqueConstraint(
            "lemma",
            "pos",
            "construction_family",
            "revision",
            name="uq_epistemic_lexicon_revision_key",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'needs_review', 'policy_conflict_hold', "
            "'rejected', 'superseded')",
            name="ck_epistemic_lexicon_status",
        ),
        CheckConstraint(
            "tier IN ('low', 'moderate', 'high', 'absolute')",
            name="ck_epistemic_lexicon_tier",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_epistemic_lexicon_confidence",
        ),
        CheckConstraint(
            "review_reason IS NULL OR review_reason IN "
            "('low_confidence', 'tier_disagreement', 'locked_neutral_policy')",
            name="ck_epistemic_lexicon_review_reason",
        ),
        Index(
            "uq_epistemic_lexicon_active_key",
            "lemma",
            "pos",
            "construction_family",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_epistemic_lexicon_status", "status"),
    )

    lemma: Mapped[str] = mapped_column(String(96))
    pos: Mapped[str] = mapped_column(String(16))
    construction_family: Mapped[str] = mapped_column(String(96))
    revision: Mapped[int] = mapped_column(Integer)
    tier: Mapped[str] = mapped_column(String(16))
    score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    run1_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    run1_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    run1_rationale: Mapped[str | None] = mapped_column(String(240), nullable=True)
    run2_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    run2_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    run2_rationale: Mapped[str | None] = mapped_column(String(240), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), default="null")
    model: Mapped[str] = mapped_column(String(128), default="")
    prompt_version: Mapped[str] = mapped_column(String(32), default="")
    provenance: Mapped[str] = mapped_column(String(64), default="ai_assessment_pending")
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("api_clients.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EpistemicLexiconAudit(Base):
    """Append-only curator actions for epistemic lexicon revisions."""

    __tablename__ = "epistemic_lexicon_audit"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("epistemic_lexicon_entries.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("api_clients.id"))
    action: Mapped[str] = mapped_column(String(16))
    previous_status: Mapped[str] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


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
