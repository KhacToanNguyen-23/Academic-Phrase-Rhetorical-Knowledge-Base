"""Bind staff to verified Google identities."""

import sqlalchemy as sa
from alembic import op

revision = "0016_google_login"
down_revision = "0015_email_login"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("api_clients", sa.Column("google_subject", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_api_clients_google_subject", "api_clients", ["google_subject"])


def downgrade():
    op.drop_constraint("uq_api_clients_google_subject", "api_clients", type_="unique")
    op.drop_column("api_clients", "google_subject")
