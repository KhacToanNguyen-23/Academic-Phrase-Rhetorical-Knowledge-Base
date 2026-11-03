"""Add import batch ids to articles and the approved phrase store."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_extraction_batches"
down_revision = "0005_candidate_occurrences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "articles", sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index("ix_articles_import_batch_id", "articles", ["import_batch_id"])
    op.create_table(
        "approved_phrases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("canonical_frame", sa.Text(), nullable=False),
        sa.Column("slots", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("epistemic_strength", sa.String(32)),
        sa.Column("cluster_key", sa.String(255)),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("articles.id")),
        sa.Column(
            "journal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_profiles.id")
        ),
        sa.Column(
            "source_sentence_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("comment", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_clients.id")),
    )
    op.create_index("ix_approved_phrases_journal_id", "approved_phrases", ["journal_id"])
    op.create_index("ix_approved_phrases_article_id", "approved_phrases", ["article_id"])


def downgrade() -> None:
    op.drop_index("ix_approved_phrases_article_id", table_name="approved_phrases")
    op.drop_index("ix_approved_phrases_journal_id", table_name="approved_phrases")
    op.drop_table("approved_phrases")
    op.drop_index("ix_articles_import_batch_id", table_name="articles")
    op.drop_column("articles", "import_batch_id")
