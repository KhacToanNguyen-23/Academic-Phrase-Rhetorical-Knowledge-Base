"""Store genre compatibility on each taxonomy section."""

from alembic import op

revision = "0006_section_genre_compatibility"
down_revision = "0005_candidate_occurrences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE sections ADD COLUMN compatible_genres JSONB NOT NULL DEFAULT '[]'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE sections DROP COLUMN IF EXISTS compatible_genres")
