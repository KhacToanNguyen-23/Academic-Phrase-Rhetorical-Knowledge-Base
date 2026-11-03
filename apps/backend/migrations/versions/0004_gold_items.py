"""Add text-free gold item references and label state."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_gold_items"
down_revision = "0003_import_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gold_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "article_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sentence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sentences.id", ondelete="SET NULL"),
        ),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("section_at_sampling", sa.String(64), nullable=False),
        sa.Column("split", sa.String(8), nullable=False),
        sa.Column("sample_batch", sa.String(64), nullable=False),
        sa.Column("guideline_version", sa.String(32), nullable=False),
        sa.Column("ai_labels", postgresql.JSONB()),
        sa.Column("ai_model", sa.String(128)),
        sa.Column("ai_prompt_version", sa.String(32)),
        sa.Column("ai_labeled_at", sa.DateTime(timezone=True)),
        sa.Column("final_labels", postgresql.JSONB()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_clients.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_clients.id")),
        sa.CheckConstraint(
            "char_start >= 0 AND char_end > char_start", name="ck_gold_items_offsets"
        ),
        sa.CheckConstraint("split IN ('dev', 'test')", name="ck_gold_items_split"),
        sa.CheckConstraint(
            "status IN ('pending_ai', 'draft', 'approved', 'rejected', 'label_failed', 'stale')",
            name="ck_gold_items_status",
        ),
    )
    op.create_index(
        "ix_gold_items_batch_status_split", "gold_items", ["sample_batch", "status", "split"]
    )


def downgrade() -> None:
    op.drop_index("ix_gold_items_batch_status_split", table_name="gold_items")
    op.drop_table("gold_items")
