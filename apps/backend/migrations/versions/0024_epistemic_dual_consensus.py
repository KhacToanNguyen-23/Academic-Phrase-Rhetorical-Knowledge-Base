"""Store dual AI evaluations and consensus review states."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_epistemic_dual_consensus"
down_revision: str | None = "0023_epistemic_lexicon"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "epistemic_lexicon_entries", "status", existing_type=sa.String(16), type_=sa.String(32)
    )
    op.drop_constraint("ck_epistemic_lexicon_status", "epistemic_lexicon_entries", type_="check")
    op.create_check_constraint(
        "ck_epistemic_lexicon_status",
        "epistemic_lexicon_entries",
        "status IN ('pending', 'active', 'needs_review', 'policy_conflict_hold', "
        "'rejected', 'superseded')",
    )
    op.add_column("epistemic_lexicon_entries", sa.Column("run1_tier", sa.String(16)))
    op.add_column("epistemic_lexicon_entries", sa.Column("run1_confidence", sa.Float()))
    op.add_column("epistemic_lexicon_entries", sa.Column("run1_rationale", sa.String(240)))
    op.add_column("epistemic_lexicon_entries", sa.Column("run2_tier", sa.String(16)))
    op.add_column("epistemic_lexicon_entries", sa.Column("run2_confidence", sa.Float()))
    op.add_column("epistemic_lexicon_entries", sa.Column("run2_rationale", sa.String(240)))
    op.add_column("epistemic_lexicon_entries", sa.Column("review_reason", sa.String(32)))
    op.create_check_constraint(
        "ck_epistemic_lexicon_run_confidence",
        "epistemic_lexicon_entries",
        "(run1_confidence IS NULL OR (run1_confidence >= 0 AND run1_confidence <= 1)) "
        "AND (run2_confidence IS NULL OR (run2_confidence >= 0 AND run2_confidence <= 1))",
    )
    op.create_check_constraint(
        "ck_epistemic_lexicon_run_tier",
        "epistemic_lexicon_entries",
        "(run1_tier IS NULL OR run1_tier IN ('low', 'moderate', 'high', 'absolute')) "
        "AND (run2_tier IS NULL OR run2_tier IN ('low', 'moderate', 'high', 'absolute'))",
    )
    op.create_check_constraint(
        "ck_epistemic_lexicon_review_reason",
        "epistemic_lexicon_entries",
        "review_reason IS NULL OR review_reason IN "
        "('low_confidence', 'tier_disagreement', 'locked_neutral_policy')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE epistemic_lexicon_entries SET status = 'pending' "
        "WHERE status IN ('needs_review', 'policy_conflict_hold')"
    )
    op.drop_constraint(
        "ck_epistemic_lexicon_review_reason", "epistemic_lexicon_entries", type_="check"
    )
    op.drop_constraint("ck_epistemic_lexicon_run_tier", "epistemic_lexicon_entries", type_="check")
    op.drop_constraint(
        "ck_epistemic_lexicon_run_confidence", "epistemic_lexicon_entries", type_="check"
    )
    op.drop_column("epistemic_lexicon_entries", "review_reason")
    op.drop_column("epistemic_lexicon_entries", "run2_rationale")
    op.drop_column("epistemic_lexicon_entries", "run2_confidence")
    op.drop_column("epistemic_lexicon_entries", "run2_tier")
    op.drop_column("epistemic_lexicon_entries", "run1_rationale")
    op.drop_column("epistemic_lexicon_entries", "run1_confidence")
    op.drop_column("epistemic_lexicon_entries", "run1_tier")
    op.drop_constraint("ck_epistemic_lexicon_status", "epistemic_lexicon_entries", type_="check")
    op.create_check_constraint(
        "ck_epistemic_lexicon_status",
        "epistemic_lexicon_entries",
        "status IN ('pending', 'active', 'rejected', 'superseded')",
    )
    op.alter_column(
        "epistemic_lexicon_entries", "status", existing_type=sa.String(32), type_=sa.String(16)
    )
