"""Persist versioned epistemic lexicon assessments."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_epistemic_lexicon"
down_revision: str | None = "0022_merge_candidate_labels_apb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "epistemic_lexicon_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lemma", sa.String(length=96), nullable=False),
        sa.Column("pos", sa.String(length=16), nullable=False),
        sa.Column("construction_family", sa.String(length=96), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("provider", sa.String(length=32), server_default="null", nullable=False),
        sa.Column("model", sa.String(length=128), server_default="", nullable=False),
        sa.Column("prompt_version", sa.String(length=32), server_default="", nullable=False),
        sa.Column(
            "provenance",
            sa.String(length=64),
            server_default="ai_assessment_pending",
            nullable=False,
        ),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'rejected', 'superseded')",
            name="ck_epistemic_lexicon_status",
        ),
        sa.CheckConstraint(
            "tier IN ('low', 'moderate', 'high', 'absolute')",
            name="ck_epistemic_lexicon_tier",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_epistemic_lexicon_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["api_clients.id"],
            name="fk_epistemic_lexicon_entries_created_by_api_clients",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["api_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "lemma",
            "pos",
            "construction_family",
            "revision",
            name="uq_epistemic_lexicon_revision_key",
        ),
    )
    op.create_index(
        "uq_epistemic_lexicon_active_key",
        "epistemic_lexicon_entries",
        ["lemma", "pos", "construction_family"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_epistemic_lexicon_status", "epistemic_lexicon_entries", ["status"])
    op.create_table(
        "epistemic_lexicon_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("previous_status", sa.String(length=16), nullable=False),
        sa.Column("new_status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "action IN ('activate', 'reject', 'deactivate')",
            name="ck_epistemic_lexicon_audit_action",
        ),
        sa.ForeignKeyConstraint(["entry_id"], ["epistemic_lexicon_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["api_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_epistemic_lexicon_audit_entry_id", "epistemic_lexicon_audit", ["entry_id"])


def downgrade() -> None:
    op.drop_index("ix_epistemic_lexicon_audit_entry_id", table_name="epistemic_lexicon_audit")
    op.drop_table("epistemic_lexicon_audit")
    op.drop_index("ix_epistemic_lexicon_status", table_name="epistemic_lexicon_entries")
    op.drop_index("uq_epistemic_lexicon_active_key", table_name="epistemic_lexicon_entries")
    op.drop_table("epistemic_lexicon_entries")
