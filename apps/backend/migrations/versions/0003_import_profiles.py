"""Add curator import profiles and job results."""

from alembic import op

revision = "0003_import_profiles"
down_revision = "0002_article_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE import_profiles (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL UNIQUE,
        source VARCHAR(64) NOT NULL DEFAULT 'slr',
        filters JSONB NOT NULL DEFAULT '{}'::jsonb,
        artifact_kinds JSONB NOT NULL DEFAULT '[]'::jsonb,
        batch_limit INTEGER NOT NULL DEFAULT 25,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by UUID REFERENCES api_clients(id))"""
    )
    op.execute("ALTER TABLE jobs ADD COLUMN result JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS result")
    op.execute("DROP TABLE IF EXISTS import_profiles")
