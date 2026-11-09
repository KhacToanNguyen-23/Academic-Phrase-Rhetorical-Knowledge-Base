"""Merge authentication and vocabulary migration heads."""

revision = "0017_merge_auth_and_vocab"
down_revision = ("0016_google_login", "0015_merge_vocab_research")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join the authentication and vocabulary migration branches."""


def downgrade() -> None:
    """Restore the independent migration heads."""
