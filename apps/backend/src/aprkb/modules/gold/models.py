"""Gold annotation records store offsets and hashes, never source sentence text."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, MutableEntityMixin


class GoldItem(MutableEntityMixin, Base):
    __tablename__ = "gold_items"
    __table_args__ = (Index("ix_gold_items_batch_status_split", "sample_batch", "status", "split"),)

    article_id: Mapped[UUID] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    sentence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sentences.id", ondelete="SET NULL"), nullable=True
    )
    char_start: Mapped[int]
    char_end: Mapped[int]
    text_sha256: Mapped[str] = mapped_column(String(64))
    section_at_sampling: Mapped[str] = mapped_column(String(64), default="OTHER")
    split: Mapped[str] = mapped_column(String(8))
    sample_batch: Mapped[str] = mapped_column(String(64))
    guideline_version: Mapped[str] = mapped_column(String(32), default="v0")
    ai_labels: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ai_prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_labeled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_labels: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending_ai")
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("api_clients.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
