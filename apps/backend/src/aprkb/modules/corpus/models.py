"""SQLAlchemy persistence models for the corpus domain."""

from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates

from aprkb.core.db import Base, EntityMixin, MutableEntityMixin
from aprkb.modules.corpus.identity import normalize_doi, title_identity


class License(EntityMixin, Base):
    __tablename__ = "licenses"
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    allows_mining: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_display: Mapped[bool] = mapped_column(Boolean, default=False)


class ImportProfile(MutableEntityMixin, Base):
    __tablename__ = "import_profiles"
    name: Mapped[str] = mapped_column(String(255), unique=True)
    source: Mapped[str] = mapped_column(String(64), default="slr")
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    artifact_kinds: Mapped[list[str]] = mapped_column(JSONB, default=list)
    batch_limit: Mapped[int] = mapped_column(Integer, default=25)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Article(MutableEntityMixin, Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_articles_source_external_id"),
    )
    # "upload" for manual uploads; otherwise the ArticleSource name that imported it.
    source: Mapped[str] = mapped_column(String(64), default="upload", server_default="upload")
    external_id: Mapped[str | None] = mapped_column(String(255))
    doi: Mapped[str | None] = mapped_column(String(255), unique=True)
    title: Mapped[str | None] = mapped_column(Text)
    doi_key: Mapped[str | None] = mapped_column(String(255), index=True)
    title_key: Mapped[str | None] = mapped_column(String(64), index=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    journal_id: Mapped[UUID | None] = mapped_column(ForeignKey("journal_profiles.id"))
    genre_id: Mapped[UUID | None] = mapped_column(ForeignKey("article_genres.id"))
    license_id: Mapped[UUID] = mapped_column(ForeignKey("licenses.id"))
    blob_key: Mapped[str] = mapped_column(String(1024))
    ingest_status: Mapped[str] = mapped_column(String(32), default="pending")
    # Id of the first import job of one "Lay bai bao" run; continuation jobs inherit it.
    import_batch_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)

    @validates("doi", "title")
    def set_identity_key(self, key: str, value: str | None) -> str | None:
        if key == "doi":
            self.doi_key = normalize_doi(value)
        else:
            self.title_key = title_identity(value)
        return value


class ArticleSection(EntityMixin, Base):
    __tablename__ = "article_sections"
    article_id: Mapped[UUID] = mapped_column(ForeignKey("articles.id"))
    section_code: Mapped[str | None] = mapped_column(String(64))
    heading: Mapped[str | None] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer)


class Sentence(EntityMixin, Base):
    __tablename__ = "sentences"
    article_id: Mapped[UUID] = mapped_column(ForeignKey("articles.id"))
    article_section_id: Mapped[UUID | None] = mapped_column(ForeignKey("article_sections.id"))
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
