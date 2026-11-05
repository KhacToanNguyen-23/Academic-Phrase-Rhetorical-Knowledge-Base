"""Merge the existing application head with the vocabulary branch."""

from collections.abc import Sequence

revision: str = "0009_merge_vocabulary"
down_revision: str | tuple[str, str] | None = ("0008_merge_heads", "0007_vocabulary")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge both migration branches without additional schema changes."""


def downgrade() -> None:
    """Split the migration graph back into its two parent heads."""
