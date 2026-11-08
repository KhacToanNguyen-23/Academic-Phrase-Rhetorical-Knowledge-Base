"""Merge the job operations branch with the candidate cluster uniqueness branch."""

from collections.abc import Sequence

revision: str = "0014_merge_jobs_and_cluster"
down_revision: str | tuple[str, str] | None = (
    "0012_candidate_cluster_unique",
    "0013_job_operations",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge both migration branches without additional schema changes."""


def downgrade() -> None:
    """Split the migration graph back into its two parent heads."""
