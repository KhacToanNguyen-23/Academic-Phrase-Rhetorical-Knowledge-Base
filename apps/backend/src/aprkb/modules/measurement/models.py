"""Persistence models for the separate Metric & Measurement catalog (ADR-0015)."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base


class MeasurementEntry(Base):
    __tablename__ = "measurement_entries"
    __table_args__ = (
        CheckConstraint("kind IN ('metric', 'method', 'protocol')", name="ck_measurement_kind"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    definition: Mapped[str] = mapped_column(Text)
    formula: Mapped[str | None] = mapped_column(Text)
    scale: Mapped[str | None] = mapped_column(String(200))
    value_range: Mapped[str | None] = mapped_column(String(120))
    usage_note: Mapped[str | None] = mapped_column(Text)
    example: Mapped[str | None] = mapped_column(Text)
    catalog_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MeasurementRelation(Base):
    __tablename__ = "measurement_relations"
    __table_args__ = (
        UniqueConstraint("from_entry_id", "relation", "to_entry_id", name="uq_measurement_rel"),
        CheckConstraint("from_entry_id <> to_entry_id", name="ck_measurement_rel_not_self"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    from_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("measurement_entries.id", ondelete="CASCADE")
    )
    relation: Mapped[str] = mapped_column(String(32))
    to_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("measurement_entries.id", ondelete="CASCADE")
    )


class MeasurementSlotLink(Base):
    """Reviewed suggestion: an entry may fill one slot of one phrase pattern."""

    __tablename__ = "measurement_slot_links"
    __table_args__ = (
        UniqueConstraint("entry_id", "pattern_id", "slot_name", name="uq_measurement_slot_link"),
        CheckConstraint(
            "review_status IN ('proposed', 'approved', 'rejected')",
            name="ck_measurement_slot_link_status",
        ),
        Index("ix_measurement_slot_links_pattern_slot", "pattern_id", "slot_name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    entry_id: Mapped[UUID] = mapped_column(ForeignKey("measurement_entries.id", ondelete="CASCADE"))
    pattern_id: Mapped[UUID] = mapped_column(ForeignKey("phrase_patterns.id", ondelete="CASCADE"))
    slot_name: Mapped[str] = mapped_column(String(64))
    review_status: Mapped[str] = mapped_column(String(16), default="proposed")
    proposed_by: Mapped[UUID | None] = mapped_column(ForeignKey("api_clients.id"))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("api_clients.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MeasurementImportRun(Base):
    __tablename__ = "measurement_import_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    content_sha256: Mapped[str] = mapped_column(String(64))
    catalog_version: Mapped[str] = mapped_column(String(32))
    entry_count: Mapped[int] = mapped_column(Integer)
    relation_count: Mapped[int] = mapped_column(Integer)
    imported_by: Mapped[UUID | None] = mapped_column(ForeignKey("api_clients.id"))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
