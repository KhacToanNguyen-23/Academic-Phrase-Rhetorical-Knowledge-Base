"""Require an explicit license policy for third-party processing."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_license_external_processing"
down_revision: str | None = "0025_epistemic_audit_width"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "licenses",
        sa.Column(
            "allows_external_processing",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("licenses", "allows_external_processing")
