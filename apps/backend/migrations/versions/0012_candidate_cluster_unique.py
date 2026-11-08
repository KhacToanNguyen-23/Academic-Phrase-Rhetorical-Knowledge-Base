"""Keep one candidate per cluster key so new sources are appended to it."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_candidate_cluster_unique"
down_revision: str | tuple[str, str] | None = "0011_merge_nlp_ingest_features"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Refuse to guess: merging reviewed duplicates needs a person, so fail with a clear count."""
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM (SELECT cluster_key FROM candidates "
                "WHERE cluster_key IS NOT NULL GROUP BY cluster_key HAVING count(*) > 1) AS d"
            )
        )
        .scalar_one()
    )
    if duplicates:
        raise RuntimeError(f"{duplicates} cluster keys repeat; merge those candidates first")
    op.create_unique_constraint("uq_candidates_cluster_key", "candidates", ["cluster_key"])


def downgrade() -> None:
    op.drop_constraint("uq_candidates_cluster_key", "candidates", type_="unique")
