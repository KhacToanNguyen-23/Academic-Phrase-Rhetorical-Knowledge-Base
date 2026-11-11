"""Allow audit rows to record the full epistemic review status names."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_epistemic_audit_width"
down_revision: str | None = "0024_epistemic_dual_consensus"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "epistemic_lexicon_audit",
        "previous_status",
        existing_type=sa.String(16),
        type_=sa.String(32),
    )
    op.alter_column(
        "epistemic_lexicon_audit",
        "new_status",
        existing_type=sa.String(16),
        type_=sa.String(32),
    )


def downgrade() -> None:
    # Keep the wider columns: an audit row may already contain a 20-character hold status.
    pass
