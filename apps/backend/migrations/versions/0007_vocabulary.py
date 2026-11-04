"""Add Academic Vocabulary List tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_vocabulary"
down_revision = "0006_extraction_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vocab_lemmas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_clients.id")),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("word", sa.String(128), nullable=False),
        sa.Column("pos", sa.String(4), nullable=False),
        sa.Column("rank", sa.Integer()),
        sa.Column("band", sa.Integer()),
        sa.Column("status", sa.String(8)),
        sa.Column("coca_all", sa.Integer()),
        sa.Column("coca_acad", sa.Integer()),
        sa.Column("ratio", sa.Float()),
        sa.Column("disp", sa.Float()),
        sa.Column("range", sa.Integer()),
        sa.Column("is_core", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("domains", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.UniqueConstraint("word", "pos", name="uq_vocab_lemmas_word_pos"),
    )
    op.create_index("ix_vocab_lemmas_rank", "vocab_lemmas", ["rank"])
    op.create_index(
        "ix_vocab_lemmas_word_prefix",
        "vocab_lemmas",
        [sa.text("word text_pattern_ops")],
    )

    op.create_table(
        "vocab_lemma_domain_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_clients.id")),
        sa.Column(
            "lemma_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vocab_lemmas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(8), nullable=False),
        sa.Column("freq", sa.Integer(), nullable=False),
        sa.Column("relative_ratio", sa.Float(), nullable=False),
        sa.UniqueConstraint("lemma_id", "domain", name="uq_vocab_domain_stats_lemma_domain"),
    )

    op.create_table(
        "vocab_families",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_clients.id")),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("headword", sa.String(128), nullable=False, unique=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("family_freq", sa.Integer(), nullable=False),
    )

    op.create_table(
        "vocab_family_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_clients.id")),
        sa.Column(
            "family_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vocab_families.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lemma_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vocab_lemmas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("freq", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(4), nullable=False),
        sa.UniqueConstraint("family_id", "lemma_id", name="uq_vocab_family_members_family_lemma"),
    )
    op.create_index("ix_vocab_family_members_lemma_id", "vocab_family_members", ["lemma_id"])

    op.create_table(
        "vocab_import_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_clients.id")),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("rows_read", sa.Integer(), nullable=False),
        sa.Column("inserted", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_vocab_import_runs_created_at", "vocab_import_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_vocab_import_runs_created_at", table_name="vocab_import_runs")
    op.drop_table("vocab_import_runs")
    op.drop_index("ix_vocab_family_members_lemma_id", table_name="vocab_family_members")
    op.drop_table("vocab_family_members")
    op.drop_table("vocab_families")
    op.drop_table("vocab_lemma_domain_stats")
    op.drop_index("ix_vocab_lemmas_word_prefix", table_name="vocab_lemmas")
    op.drop_index("ix_vocab_lemmas_rank", table_name="vocab_lemmas")
    op.drop_table("vocab_lemmas")
