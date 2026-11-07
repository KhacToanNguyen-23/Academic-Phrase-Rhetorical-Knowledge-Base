"""Bound retries and fence worker ownership without requeueing historical failures."""

import sqlalchemy as sa
from alembic import op

revision = "0012_job_retry"
down_revision = "0011_corpus_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="4")
    )
    op.add_column("jobs", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("lock_token", sa.Uuid(), nullable=True))
    op.add_column("jobs", sa.Column("error_code", sa.String(64), nullable=True))
    op.create_index("ix_jobs_next_attempt_at", "jobs", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_next_attempt_at", table_name="jobs")
    for column in ("error_code", "lock_token", "next_attempt_at", "max_attempts"):
        op.drop_column("jobs", column)
