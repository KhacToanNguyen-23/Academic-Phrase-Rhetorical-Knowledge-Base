"""PDF text fingerprints, reviewed metadata and page provenance (FR-04)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_pdf_import"
down_revision = "0013_job_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("pdf_text_sha256", sa.String(64)))
    op.create_index("ix_articles_pdf_text_sha256", "articles", ["pdf_text_sha256"])
    op.add_column(
        "articles", sa.Column("authors", postgresql.JSONB(), nullable=False, server_default="[]")
    )
    op.add_column("articles", sa.Column("publication_year", sa.Integer()))
    op.add_column("articles", sa.Column("source_url", sa.String(2048)))
    op.add_column("articles", sa.Column("page_count", sa.Integer()))
    op.add_column("articles", sa.Column("parser_version", sa.String(128)))
    op.add_column(
        "articles",
        sa.Column("metadata_provenance", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column("article_sections", sa.Column("page_number", sa.Integer()))


def downgrade() -> None:
    op.drop_column("article_sections", "page_number")
    op.drop_index("ix_articles_pdf_text_sha256", table_name="articles")
    for column in (
        "metadata_provenance",
        "parser_version",
        "page_count",
        "source_url",
        "publication_year",
        "authors",
        "pdf_text_sha256",
    ):
        op.drop_column("articles", column)
