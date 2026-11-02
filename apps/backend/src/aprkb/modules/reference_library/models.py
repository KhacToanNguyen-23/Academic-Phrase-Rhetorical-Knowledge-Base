"""Persistence models for quarantined internal reference material."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
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


class ReferenceSource(Base):
    __tablename__ = "reference_sources"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    source_url: Mapped[str] = mapped_column(Text)
    license_status: Mapped[str] = mapped_column(String(80))
    rights_status: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(80))
    content_sha256: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReferenceCategory(Base):
    __tablename__ = "reference_categories"
    __table_args__ = (
        UniqueConstraint("source_id", "slug", name="uq_reference_category_source_slug"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("reference_sources.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(Text)


class ReferenceEntry(Base):
    __tablename__ = "reference_entries"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("reference_categories.id", ondelete="CASCADE")
    )
    heading: Mapped[str] = mapped_column(Text)
    heading_position: Mapped[int] = mapped_column(Integer)
    block_index: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))
    text: Mapped[str | None] = mapped_column(Text)
    cells: Mapped[list[list[str]] | None] = mapped_column(JSONB)
    search_text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


Index(
    "ix_reference_entries_search_text_gin",
    func.to_tsvector("simple", ReferenceEntry.search_text),
    postgresql_using="gin",
)
