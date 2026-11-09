"""Store sentence NLP features and the engine used for article ingest."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_nlp_ingest_features"
down_revision = "0008_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sentences",
        sa.Column("nlp_features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("sentences", sa.Column("boundary_source", sa.String(length=64), nullable=True))
    op.add_column(
        "articles",
        sa.Column("nlp_engine", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("articles", "nlp_engine")
    op.drop_column("sentences", "boundary_source")
    op.drop_column("sentences", "nlp_features")
