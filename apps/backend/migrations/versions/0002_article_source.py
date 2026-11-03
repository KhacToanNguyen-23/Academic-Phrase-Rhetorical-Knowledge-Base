"""Track which source imported each article (ADR-0005)."""

from alembic import op

revision = "0002_article_source"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE articles ADD COLUMN source VARCHAR(64) DEFAULT 'upload' NOT NULL")
    op.execute("ALTER TABLE articles ADD COLUMN external_id VARCHAR(255)")
    op.execute(
        "ALTER TABLE articles ADD CONSTRAINT uq_articles_source_external_id "
        "UNIQUE (source, external_id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE articles DROP CONSTRAINT IF EXISTS uq_articles_source_external_id")
    op.execute("ALTER TABLE articles DROP COLUMN IF EXISTS external_id")
    op.execute("ALTER TABLE articles DROP COLUMN IF EXISTS source")
