"""SQLAlchemy persistence models for the patterns domain."""

from typing import Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, EntityMixin, MutableEntityMixin


class PhrasePattern(MutableEntityMixin, Base):
    __tablename__ = "phrase_patterns"
    intent_id: Mapped[UUID] = mapped_column(ForeignKey("intents.id"))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    current_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pattern_versions.id", use_alter=True, name="fk_pattern_current_version")
    )


class PatternVersion(EntityMixin, Base):
    __tablename__ = "pattern_versions"
    __table_args__ = (UniqueConstraint("pattern_id", "version_no"),)
    pattern_id: Mapped[UUID] = mapped_column(ForeignKey("phrase_patterns.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    canonical_frame: Mapped[str] = mapped_column(Text)
    slots: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    epistemic_strength: Mapped[str] = mapped_column(String(32))
    claim_type: Mapped[str] = mapped_column(String(64))
    change_note: Mapped[str | None] = mapped_column(Text)


class PhraseVariant(EntityMixin, Base):
    __tablename__ = "phrase_variants"
    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    text: Mapped[str] = mapped_column(Text)
    register: Mapped[str | None] = mapped_column(String(64))


class UsageConstraint(EntityMixin, Base):
    __tablename__ = "usage_constraints"
    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"), unique=True)
    evidence_min: Mapped[str | None] = mapped_column(String(64))
    forbidden_contexts: Mapped[list[str]] = mapped_column(JSONB, default=list)
    allowed_sections: Mapped[list[str]] = mapped_column(JSONB, default=list)
    allowed_genres: Mapped[list[str]] = mapped_column(JSONB, default=list)


class EvidenceProvenance(EntityMixin, Base):
    __tablename__ = "evidence_provenances"
    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    source_type: Mapped[str] = mapped_column(String(16))
    article_id: Mapped[UUID | None] = mapped_column(ForeignKey("articles.id"))
    sentence_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid(as_uuid=True)), default=list)
    license_id: Mapped[UUID | None] = mapped_column(ForeignKey("licenses.id"))


class DisciplineAffinity(EntityMixin, Base):
    __tablename__ = "discipline_affinities"
    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    discipline_code: Mapped[str] = mapped_column(String(128))
    score: Mapped[float] = mapped_column(Float)


class ReviewDecision(EntityMixin, Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        CheckConstraint(
            "(candidate_id IS NOT NULL AND pattern_version_id IS NULL) OR "
            "(candidate_id IS NULL AND pattern_version_id IS NOT NULL)",
            name="ck_review_decision_single_target",
        ),
        CheckConstraint("round IN (1, 2)", name="ck_review_decision_round"),
    )
    candidate_id: Mapped[UUID | None] = mapped_column(ForeignKey("candidates.id"))
    pattern_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("pattern_versions.id"))
    round: Mapped[int] = mapped_column(SmallInteger)
    decision: Mapped[str] = mapped_column(String(32))
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("api_clients.id"))
    comment: Mapped[str | None] = mapped_column(Text)
