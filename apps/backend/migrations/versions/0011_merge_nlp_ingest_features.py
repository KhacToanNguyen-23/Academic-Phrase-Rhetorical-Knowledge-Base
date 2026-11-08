"""Merge the NLP ingest features branch with the vocabulary and pack provenance heads."""

from collections.abc import Sequence

revision: str = "0011_merge_nlp_ingest_features"
down_revision: str | tuple[str, str] | None = (
    "0010_merge_vocabulary_and_pack",
    "0009_nlp_ingest_features",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge both migration branches without additional schema changes."""


def downgrade() -> None:
    """Split the migration graph back into its two parent heads."""
