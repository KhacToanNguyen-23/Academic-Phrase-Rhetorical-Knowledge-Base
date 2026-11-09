"""Add the separate Metric & Measurement catalog (ADR-0015)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_measurement_catalog"
down_revision = "0015_merge_vocab_research"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "measurement_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("aliases", postgresql.JSONB(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("formula", sa.Text()),
        sa.Column("scale", sa.String(200)),
        sa.Column("value_range", sa.String(120)),
        sa.Column("usage_note", sa.Text()),
        sa.Column("example", sa.Text()),
        sa.Column("catalog_version", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("kind IN ('metric', 'method', 'protocol')", name="ck_measurement_kind"),
    )
    op.create_table(
        "measurement_relations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "from_entry_id",
            sa.Uuid(),
            sa.ForeignKey("measurement_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation", sa.String(32), nullable=False),
        sa.Column(
            "to_entry_id",
            sa.Uuid(),
            sa.ForeignKey("measurement_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("from_entry_id", "relation", "to_entry_id", name="uq_measurement_rel"),
        sa.CheckConstraint("from_entry_id <> to_entry_id", name="ck_measurement_rel_not_self"),
    )
    op.create_table(
        "measurement_slot_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "entry_id",
            sa.Uuid(),
            sa.ForeignKey("measurement_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pattern_id",
            sa.Uuid(),
            sa.ForeignKey("phrase_patterns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slot_name", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(16), nullable=False),
        sa.Column("proposed_by", sa.Uuid(), sa.ForeignKey("api_clients.id")),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("api_clients.id")),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("entry_id", "pattern_id", "slot_name", name="uq_measurement_slot_link"),
        sa.CheckConstraint(
            "review_status IN ('proposed', 'approved', 'rejected')",
            name="ck_measurement_slot_link_status",
        ),
    )
    op.create_index(
        "ix_measurement_slot_links_pattern_slot",
        "measurement_slot_links",
        ["pattern_id", "slot_name"],
    )
    op.create_table(
        "measurement_import_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("catalog_version", sa.String(32), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("relation_count", sa.Integer(), nullable=False),
        sa.Column("imported_by", sa.Uuid(), sa.ForeignKey("api_clients.id")),
        sa.Column(
            "imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("measurement_import_runs")
    op.drop_index("ix_measurement_slot_links_pattern_slot", table_name="measurement_slot_links")
    op.drop_table("measurement_slot_links")
    op.drop_table("measurement_relations")
    op.drop_table("measurement_entries")
