"""Store offline APB annotations as reviewable proposals."""

import sqlalchemy as sa
from alembic import op

revision = "0017_apb_offline_proposals"
down_revision = "0016_nullable_pattern_intent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pattern_version_apb_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("api_clients.id")),
        sa.Column(
            "pattern_version_id",
            sa.Uuid(),
            sa.ForeignKey("pattern_versions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint("status = 'proposed'", name="ck_apb_transfer_proposal_status"),
    )


def downgrade() -> None:
    op.drop_table("pattern_version_apb_proposals")
