"""Create isolated tables for internal external-reference material."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_reference_library"
down_revision = "0005_candidate_occurrences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reference_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("license_status", sa.String(length=80), nullable=False),
        sa.Column("rights_status", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "reference_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("resolved_url", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.String(length=80), nullable=False),
        sa.Column("html_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_category", sa.String(length=120), nullable=False),
        sa.Column("license_status", sa.String(length=80), nullable=False),
        sa.Column("rights_status", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("extraction_method", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["reference_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "slug", name="uq_reference_category_source_slug"),
    )
    op.create_table(
        "reference_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=False),
        sa.Column("heading_position", sa.Integer(), nullable=False),
        sa.Column("block_index", sa.Integer(), nullable=False),
        sa.Column("block_id", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("cells", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["reference_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reference_entries_search_text_gin",
        "reference_entries",
        [sa.text("to_tsvector('simple', search_text)")],
        unique=False,
        postgresql_using="gin",
    )
    op.create_table(
        "reference_taxonomy_map",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reference_category_id", sa.Uuid(), nullable=False),
        sa.Column("reference_key", sa.String(length=240), nullable=False),
        sa.Column("reference_title", sa.Text(), nullable=False),
        sa.Column("heading_position", sa.Integer(), nullable=True),
        sa.Column("target_kind", sa.String(length=32), nullable=True),
        sa.Column("target_code", sa.String(length=64), nullable=True),
        sa.Column("review_status", sa.String(length=16), nullable=True),
        sa.Column("mapped_by", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "target_kind IS NULL OR target_kind IN ('section', 'intent', 'general_function')",
            name="ck_reference_taxonomy_target_kind",
        ),
        sa.CheckConstraint(
            "review_status IS NULL OR review_status IN ('proposed', 'approved')",
            name="ck_reference_taxonomy_review_status",
        ),
        sa.CheckConstraint(
            "(target_kind IS NULL AND target_code IS NULL AND review_status IS NULL) OR "
            "(target_kind IS NOT NULL AND target_code IS NOT NULL AND review_status IS NOT NULL)",
            name="ck_reference_taxonomy_mapping_complete",
        ),
        sa.ForeignKeyConstraint(
            ["reference_category_id"], ["reference_categories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reference_category_id", "reference_key", name="uq_reference_taxonomy_key"
        ),
    )


def downgrade() -> None:
    op.drop_table("reference_taxonomy_map")
    op.drop_index("ix_reference_entries_search_text_gin", table_name="reference_entries")
    op.drop_table("reference_entries")
    op.drop_table("reference_categories")
    op.drop_table("reference_sources")
