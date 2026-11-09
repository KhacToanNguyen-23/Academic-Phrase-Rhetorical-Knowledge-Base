"""Merge the vocabulary research pilot and dev migration heads."""

revision = "0015_merge_vocab_research"
down_revision = ("0014_merge_jobs_and_cluster", "0011_vocab_research_pilot")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join both migration branches."""


def downgrade() -> None:
    """Restore both migration heads."""
