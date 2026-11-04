"""Merge the vocabulary branch with the pack provenance metadata branch."""

from collections.abc import Sequence

revision: str = "0010_merge_vocabulary_and_pack"
down_revision: str | tuple[str, str] | None = (
    "0009_merge_vocabulary",
    "0009_pack_provenance_metadata",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge both migration branches without additional schema changes."""


def downgrade() -> None:
    """Split the migration graph back into its two parent heads."""
