"""SQLAlchemy persistence models for the taxonomy domain."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, EntityMixin, MutableEntityMixin


class TaxonomyRelease(MutableEntityMixin, Base):
    __tablename__ = "taxonomy_releases"
    version: Mapped[str] = mapped_column(String(32), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Section(EntityMixin, Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("release_id", "code"),)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    order: Mapped[int] = mapped_column(Integer)
    release_id: Mapped[UUID] = mapped_column(ForeignKey("taxonomy_releases.id"))


class Move(EntityMixin, Base):
    __tablename__ = "moves"
    __table_args__ = (UniqueConstraint("section_id", "code"),)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    section_id: Mapped[UUID] = mapped_column(ForeignKey("sections.id"))


class Step(EntityMixin, Base):
    __tablename__ = "steps"
    __table_args__ = (UniqueConstraint("move_id", "code"),)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    move_id: Mapped[UUID] = mapped_column(ForeignKey("moves.id"))


class Intent(EntityMixin, Base):
    __tablename__ = "intents"
    __table_args__ = (UniqueConstraint("step_id", "code"),)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    step_id: Mapped[UUID] = mapped_column(ForeignKey("steps.id"))
    description: Mapped[str | None] = mapped_column(Text)


class ArticleGenre(EntityMixin, Base):
    __tablename__ = "article_genres"
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
