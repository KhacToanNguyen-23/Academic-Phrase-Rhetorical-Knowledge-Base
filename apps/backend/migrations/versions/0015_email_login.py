"""Organization email login and expiring staff sessions."""

import sqlalchemy as sa
from alembic import op

revision = "0015_email_login"
down_revision = "0014_merge_jobs_and_cluster"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("api_clients", sa.Column("email", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_api_clients_email", "api_clients", ["email"])
    op.add_column("api_clients", sa.Column("password_hash", sa.String(255), nullable=True))
    op.create_table(
        "staff_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("api_clients.id"), nullable=True),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("api_clients.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("staff_sessions")
    op.drop_column("api_clients", "password_hash")
    op.drop_constraint("uq_api_clients_email", "api_clients", type_="unique")
    op.drop_column("api_clients", "email")
