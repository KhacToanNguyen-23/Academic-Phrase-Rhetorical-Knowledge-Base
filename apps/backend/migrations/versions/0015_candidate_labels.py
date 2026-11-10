"""Store AI frame-label proposals separately from approved phrase patterns."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_candidate_labels"
down_revision: str | None = "0014_merge_jobs_and_cluster"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_labels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("label_code", sa.String(length=64), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="proposed", nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("needs_attention", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("agreement", sa.String(length=32), nullable=True),
        sa.Column("proposed_by_run", sa.String(length=64), nullable=True),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'confirmed', 'rejected')", name="ck_candidate_labels_status"
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_candidate_labels_confidence",
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["api_clients.id"],
            name="fk_candidate_labels_created_by_api_clients",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["api_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id", "label_code", name="uq_candidate_labels_candidate_code"
        ),
    )
    op.create_index("ix_candidate_labels_label_code", "candidate_labels", ["label_code"])
    op.create_index("ix_candidate_labels_status", "candidate_labels", ["status"])
    op.create_index("ix_candidate_labels_needs_attention", "candidate_labels", ["needs_attention"])


def downgrade() -> None:
    op.drop_index("ix_candidate_labels_needs_attention", table_name="candidate_labels")
    op.drop_index("ix_candidate_labels_status", table_name="candidate_labels")
    op.drop_index("ix_candidate_labels_label_code", table_name="candidate_labels")
    op.drop_table("candidate_labels")
