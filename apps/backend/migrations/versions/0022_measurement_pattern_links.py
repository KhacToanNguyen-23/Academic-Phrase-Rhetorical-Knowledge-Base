"""Allow pattern-level measurement links and record how a link was proposed (ADR-0015)."""

import sqlalchemy as sa
from alembic import op

revision = "0022_measurement_pattern_links"
down_revision = "0021_apb_offline_proposals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "measurement_slot_links", "slot_name", existing_type=sa.String(64), nullable=True
    )
    op.drop_constraint("uq_measurement_slot_link", "measurement_slot_links", type_="unique")
    op.create_index(
        "uq_measurement_slot_link_key",
        "measurement_slot_links",
        ["entry_id", "pattern_id", sa.text("coalesce(slot_name, '')")],
        unique=True,
    )
    op.add_column(
        "measurement_slot_links",
        sa.Column("origin", sa.String(16), nullable=False, server_default="manual"),
    )
    op.create_check_constraint(
        "ck_measurement_link_origin",
        "measurement_slot_links",
        "origin IN ('manual', 'term_match')",
    )


def downgrade() -> None:
    # Pattern-level links cannot be represented by the previous schema.
    op.execute("DELETE FROM measurement_slot_links WHERE slot_name IS NULL")
    op.drop_constraint("ck_measurement_link_origin", "measurement_slot_links", type_="check")
    op.drop_column("measurement_slot_links", "origin")
    op.drop_index("uq_measurement_slot_link_key", table_name="measurement_slot_links")
    op.create_unique_constraint(
        "uq_measurement_slot_link",
        "measurement_slot_links",
        ["entry_id", "pattern_id", "slot_name"],
    )
    op.alter_column(
        "measurement_slot_links", "slot_name", existing_type=sa.String(64), nullable=False
    )
