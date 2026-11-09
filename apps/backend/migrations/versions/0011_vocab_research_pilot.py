"""Store research vocabulary pilot samples and document frequencies."""

import sqlalchemy as sa
from alembic import op

revision = "0011_vocab_research_pilot"
down_revision = "0010_merge_vocabulary_and_pack"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vocab_research_groups",
        sa.Column("key", sa.String(32), primary_key=True),
        sa.Column("field_id", sa.String(20), nullable=False),
        sa.Column("field_name", sa.String(255), nullable=False),
        sa.Column("subfield_id", sa.String(20)),
        sa.Column("subfield_name", sa.String(255)),
        sa.Column("paper_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("paper_count > 0", name="ck_vocab_research_group_count"),
    )
    op.create_table(
        "vocab_lemma_research_stats",
        sa.Column(
            "group_key",
            sa.String(32),
            sa.ForeignKey("vocab_research_groups.key", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "lemma_id",
            sa.Uuid(),
            sa.ForeignKey("vocab_lemmas.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("paper_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("paper_count >= 2", name="ck_vocab_research_stat_count"),
    )


def downgrade() -> None:
    op.drop_table("vocab_lemma_research_stats")
    op.drop_table("vocab_research_groups")
