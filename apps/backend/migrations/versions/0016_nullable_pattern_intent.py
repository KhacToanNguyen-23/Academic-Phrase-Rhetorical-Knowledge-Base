"""Allow APB phrases without a legacy rhetorical intent."""

from alembic import op

revision = "0016_nullable_pattern_intent"
down_revision = "0015_academic_phrase_bank"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("phrase_patterns", "intent_id", nullable=True)


def downgrade() -> None:
    op.alter_column("phrase_patterns", "intent_id", nullable=False)
