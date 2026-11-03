"""Store metadata-only provenance carried by Offline data packs."""

import sqlalchemy as sa
from alembic import op

revision = "0009_pack_provenance_metadata"
down_revision = "0008_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evidence_provenances", sa.Column("source_sentence_count", sa.Integer(), nullable=True)
    )
    op.add_column(
        "evidence_provenances", sa.Column("occurrence_hash", sa.String(255), nullable=True)
    )
    op.add_column(
        "evidence_provenances", sa.Column("source_section_code", sa.String(64), nullable=True)
    )
    op.add_column(
        "review_decisions", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("review_decisions", "decided_at")
    op.drop_column("evidence_provenances", "source_section_code")
    op.drop_column("evidence_provenances", "occurrence_hash")
    op.drop_column("evidence_provenances", "source_sentence_count")
