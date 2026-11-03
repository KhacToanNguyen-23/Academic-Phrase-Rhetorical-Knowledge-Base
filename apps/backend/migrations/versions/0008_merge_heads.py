"""Merge the extraction and reference-library migration heads."""

from collections.abc import Sequence

revision: str = "0008_merge_heads"
down_revision: str | tuple[str, str] | None = (
    "0006_extraction_batches",
    "0007_reference_library",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge both migration branches without additional schema changes."""


def downgrade() -> None:
    """Split the migration graph back into its two parent heads."""
