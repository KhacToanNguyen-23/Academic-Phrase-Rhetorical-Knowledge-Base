"""Shared reference-table model."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from aprkb.core.db import Base, EntityMixin


class RefEnum(EntityMixin, Base):
    __tablename__ = "ref_enums"
    __table_args__ = (UniqueConstraint("group", "code"),)
    group: Mapped[str] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))
    order: Mapped[int] = mapped_column(Integer)
