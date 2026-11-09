"""Persist job attempts, operational progress and repeated-failure alerts."""

import sqlalchemy as sa
from alembic import op

revision = "0013_job_operations"
down_revision = "0012_job_retry"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("api_clients.id")),
    ]


def upgrade() -> None:
    op.add_column(
        "jobs", sa.Column("manual_retries", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("jobs", sa.Column("progress_stage", sa.String(64)))
    op.add_column("jobs", sa.Column("progress_completed", sa.Integer()))
    op.add_column("jobs", sa.Column("progress_total", sa.Integer()))
    op.create_table(
        "job_attempts",
        *_base(),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(64)),
        sa.Column("completed", sa.Integer()),
        sa.Column("total", sa.Integer()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error", sa.Text()),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("job_id", "attempt_no", name="uq_job_attempt_number"),
    )
    op.create_index("ix_job_attempts_job_id", "job_attempts", ["job_id"])
    op.create_table(
        "job_alerts",
        *_base(),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id"), nullable=False, unique=True),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(64)),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_by", sa.Uuid(), sa.ForeignKey("api_clients.id")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    # Old jobs deliberately have no invented attempt/error history.


def downgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("Job operations downgrade requires an online data preflight")
    used = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM job_attempts) OR EXISTS(SELECT 1 FROM job_alerts) "
            "OR EXISTS(SELECT 1 FROM jobs WHERE manual_retries > 0)"
        )
    )
    if used:
        raise RuntimeError(
            "Job operations history exists; use a forward fix instead of dropping it"
        )
    op.drop_table("job_alerts")
    op.drop_index("ix_job_attempts_job_id", table_name="job_attempts")
    op.drop_table("job_attempts")
    for column in ("progress_total", "progress_completed", "progress_stage", "manual_retries"):
        op.drop_column("jobs", column)
