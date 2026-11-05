"""SQLAlchemy models for the imported Academic Vocabulary List."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ARRAY, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aprkb.core.db import Base, EntityMixin, MutableEntityMixin


class VocabLemma(MutableEntityMixin, Base):
    """A normalized vocabulary lemma identified by word and part of speech."""

    __tablename__ = "vocab_lemmas"
    __table_args__ = (
        UniqueConstraint("word", "pos", name="uq_vocab_lemmas_word_pos"),
        Index("ix_vocab_lemmas_rank", "rank"),
        Index("ix_vocab_lemmas_word_prefix", "word", postgresql_ops={"word": "text_pattern_ops"}),
    )

    word: Mapped[str] = mapped_column(String(128), nullable=False)
    pos: Mapped[str] = mapped_column(String(4), nullable=False)
    rank: Mapped[int | None] = mapped_column(nullable=True)
    band: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str | None] = mapped_column(String(8), nullable=True)
    coca_all: Mapped[int | None] = mapped_column(nullable=True)
    coca_acad: Mapped[int | None] = mapped_column(nullable=True)
    ratio: Mapped[float | None] = mapped_column(nullable=True)
    disp: Mapped[float | None] = mapped_column(nullable=True)
    domain_range: Mapped[int | None] = mapped_column("range", nullable=True)
    is_core: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    domains: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default="{}"
    )

    domain_stats: Mapped[list[VocabLemmaDomainStat]] = relationship(
        back_populates="lemma", cascade="all, delete-orphan"
    )
    family_members: Mapped[list[VocabFamilyMember]] = relationship(
        back_populates="lemma", cascade="all, delete-orphan"
    )


class VocabLemmaDomainStat(EntityMixin, Base):
    """Frequency and relative ratio for a lemma in one academic domain."""

    __tablename__ = "vocab_lemma_domain_stats"
    __table_args__ = (
        UniqueConstraint("lemma_id", "domain", name="uq_vocab_domain_stats_lemma_domain"),
    )

    lemma_id: Mapped[UUID] = mapped_column(
        ForeignKey("vocab_lemmas.id", ondelete="CASCADE"), nullable=False
    )
    domain: Mapped[str] = mapped_column(String(8), nullable=False)
    freq: Mapped[int] = mapped_column(nullable=False)
    relative_ratio: Mapped[float] = mapped_column(nullable=False)

    lemma: Mapped[VocabLemma] = relationship(back_populates="domain_stats")


class VocabFamily(MutableEntityMixin, Base):
    """A word family and its source-level aggregate statistics."""

    __tablename__ = "vocab_families"

    headword: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    rank: Mapped[int] = mapped_column(nullable=False)
    family_freq: Mapped[int] = mapped_column(nullable=False)

    members: Mapped[list[VocabFamilyMember]] = relationship(
        back_populates="family", cascade="all, delete-orphan"
    )


class VocabFamilyMember(EntityMixin, Base):
    """Membership of a lemma in a word family."""

    __tablename__ = "vocab_family_members"
    __table_args__ = (
        UniqueConstraint("family_id", "lemma_id", name="uq_vocab_family_members_family_lemma"),
        Index("ix_vocab_family_members_lemma_id", "lemma_id"),
    )

    family_id: Mapped[UUID] = mapped_column(
        ForeignKey("vocab_families.id", ondelete="CASCADE"), nullable=False
    )
    lemma_id: Mapped[UUID] = mapped_column(
        ForeignKey("vocab_lemmas.id", ondelete="CASCADE"), nullable=False
    )
    freq: Mapped[int] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(String(4), nullable=False)

    family: Mapped[VocabFamily] = relationship(back_populates="members")
    lemma: Mapped[VocabLemma] = relationship(back_populates="family_members")


class VocabImportRun(EntityMixin, Base):
    """Audit-friendly summary of one vocabulary workbook import."""

    __tablename__ = "vocab_import_runs"
    __table_args__ = (Index("ix_vocab_import_runs_created_at", "created_at"),)

    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    rows_read: Mapped[int] = mapped_column(nullable=False)
    inserted: Mapped[int] = mapped_column(nullable=False)
    updated: Mapped[int] = mapped_column(nullable=False)
    skipped: Mapped[int] = mapped_column(nullable=False)
    warnings: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
