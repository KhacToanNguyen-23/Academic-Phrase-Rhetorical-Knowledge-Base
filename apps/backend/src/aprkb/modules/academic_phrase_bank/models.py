"""APB metadata attached to immutable pattern versions."""

from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, EntityMixin


class FunctionFamily(EntityMixin, Base):
    __tablename__ = "apb_function_families"
    __table_args__ = (UniqueConstraint("code", "version"),)

    code: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="proposed")


class CommunicativeFunction(EntityMixin, Base):
    __tablename__ = "apb_communicative_functions"
    __table_args__ = (UniqueConstraint("code", "version"),)

    family_id: Mapped[UUID] = mapped_column(ForeignKey("apb_function_families.id"))
    code: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="proposed")


class PatternVersionFunction(EntityMixin, Base):
    __tablename__ = "pattern_version_functions"
    __table_args__ = (
        UniqueConstraint("pattern_version_id", "function_id"),
        CheckConstraint("status IN ('proposed', 'reviewed')", name="ck_apb_function_link_status"),
    )

    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    function_id: Mapped[UUID] = mapped_column(ForeignKey("apb_communicative_functions.id"))
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    context_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PatternVersionMove(EntityMixin, Base):
    __tablename__ = "pattern_version_moves"
    __table_args__ = (UniqueConstraint("pattern_version_id", "move_id", "relation"),)

    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    move_id: Mapped[UUID] = mapped_column(ForeignKey("moves.id"))
    relation: Mapped[str] = mapped_column(String(32), default="REALIZES_MOVE")


class PatternVersionStep(EntityMixin, Base):
    __tablename__ = "pattern_version_steps"
    __table_args__ = (UniqueConstraint("pattern_version_id", "step_id", "relation"),)

    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    step_id: Mapped[UUID] = mapped_column(ForeignKey("steps.id"))
    relation: Mapped[str] = mapped_column(String(32), default="REALIZES_STEP")


class PhraseUsageProfile(EntityMixin, Base):
    __tablename__ = "phrase_usage_profiles"

    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    section_id: Mapped[UUID | None] = mapped_column(ForeignKey("sections.id"), nullable=True)
    genre_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language_code: Mapped[str] = mapped_column(String(16), default="en")
    register_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    register_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    discipline_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    audience: Mapped[str | None] = mapped_column(String(128), nullable=True)
    preferred_usage: Mapped[str | None] = mapped_column(String(32), nullable=True)


class PragmaticFeature(EntityMixin, Base):
    __tablename__ = "apb_pragmatic_features"
    __table_args__ = (UniqueConstraint("code", "version"),)

    code: Mapped[str] = mapped_column(String(64))
    facet: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="proposed")


class PatternVersionPragmaticTag(EntityMixin, Base):
    __tablename__ = "pattern_version_pragmatic_tags"
    __table_args__ = (UniqueConstraint("pattern_version_id", "feature_id"),)

    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    feature_id: Mapped[UUID] = mapped_column(ForeignKey("apb_pragmatic_features.id"))
    strength_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PhraseExample(EntityMixin, Base):
    __tablename__ = "phrase_examples"
    __table_args__ = (
        CheckConstraint(
            "example_kind IN ('positive', 'negative', 'revised')",
            name="ck_apb_phrase_example_kind",
        ),
        CheckConstraint(
            "origin_kind IN ('internal_original', 'illustrative_synthetic', 'licensed')",
            name="ck_apb_phrase_example_origin",
        ),
    )

    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    example_kind: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_kind: Mapped[str] = mapped_column(String(32), default="internal_original")
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_id: Mapped[UUID | None] = mapped_column(ForeignKey("licenses.id"), nullable=True)


class PhraseCaveat(EntityMixin, Base):
    __tablename__ = "phrase_caveats"

    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    code: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)


class PatternVersionAPBProposal(EntityMixin, Base):
    """Offline-generated APB labels retained for review, separate from published metadata."""

    __tablename__ = "pattern_version_apb_proposals"
    __table_args__ = (
        UniqueConstraint("pattern_version_id"),
        CheckConstraint("status = 'proposed'", name="ck_apb_transfer_proposal_status"),
    )

    pattern_version_id: Mapped[UUID] = mapped_column(ForeignKey("pattern_versions.id"))
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
