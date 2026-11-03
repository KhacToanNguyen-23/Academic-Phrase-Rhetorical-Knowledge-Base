"""Append-only store of phrases accepted by one reviewer on the extraction page."""

from typing import Any
from uuid import UUID

from sqlalchemy import ARRAY, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, EntityMixin


class ApprovedPhrase(EntityMixin, Base):
    """A mined frame a reviewer accepted; it never becomes a PhrasePattern by itself.

    Input for the journal fingerprint (TODO(owner, FR-07.6)). Rows are never updated or deleted.
    """

    __tablename__ = "approved_phrases"
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), unique=True)
    canonical_frame: Mapped[str] = mapped_column(Text)
    slots: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    epistemic_strength: Mapped[str | None] = mapped_column(String(32))
    cluster_key: Mapped[str | None] = mapped_column(String(255))
    article_id: Mapped[UUID | None] = mapped_column(ForeignKey("articles.id"))
    journal_id: Mapped[UUID | None] = mapped_column(ForeignKey("journal_profiles.id"))
    source_sentence_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid(as_uuid=True)), default=list)
    comment: Mapped[str | None] = mapped_column(Text)
