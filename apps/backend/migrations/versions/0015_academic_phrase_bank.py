"""Add version-scoped Academic Phrase Bank metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0015_academic_phrase_bank"
down_revision = "0014_merge_jobs_and_cluster"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("api_clients.id")),
    ]


def upgrade() -> None:
    op.create_table(
        "apb_function_families",
        *_base(),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
        sa.UniqueConstraint("code", "version", name="uq_apb_function_family_version"),
    )
    op.create_table(
        "apb_communicative_functions",
        *_base(),
        sa.Column(
            "family_id", sa.Uuid(), sa.ForeignKey("apb_function_families.id"), nullable=False
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
        sa.UniqueConstraint("code", "version", name="uq_apb_function_version"),
    )
    op.create_index(
        "ix_apb_communicative_functions_family_id",
        "apb_communicative_functions",
        ["family_id"],
    )
    op.create_table(
        "apb_pragmatic_features",
        *_base(),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("facet", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
        sa.UniqueConstraint("code", "version", name="uq_apb_pragmatic_feature_version"),
    )
    op.create_table(
        "pattern_version_functions",
        *_base(),
        sa.Column(
            "pattern_version_id", sa.Uuid(), sa.ForeignKey("pattern_versions.id"), nullable=False
        ),
        sa.Column(
            "function_id",
            sa.Uuid(),
            sa.ForeignKey("apb_communicative_functions.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
        sa.Column("context_note", sa.Text()),
        sa.CheckConstraint(
            "status IN ('proposed', 'reviewed')", name="ck_apb_function_link_status"
        ),
        sa.UniqueConstraint(
            "pattern_version_id", "function_id", name="uq_pattern_version_function"
        ),
    )
    op.create_index(
        "ix_pattern_version_functions_function_id", "pattern_version_functions", ["function_id"]
    )
    op.create_table(
        "pattern_version_moves",
        *_base(),
        sa.Column(
            "pattern_version_id", sa.Uuid(), sa.ForeignKey("pattern_versions.id"), nullable=False
        ),
        sa.Column("move_id", sa.Uuid(), sa.ForeignKey("moves.id"), nullable=False),
        sa.Column("relation", sa.String(32), nullable=False, server_default="REALIZES_MOVE"),
        sa.UniqueConstraint(
            "pattern_version_id", "move_id", "relation", name="uq_pattern_version_move_relation"
        ),
    )
    op.create_index("ix_pattern_version_moves_move_id", "pattern_version_moves", ["move_id"])
    op.create_table(
        "pattern_version_steps",
        *_base(),
        sa.Column(
            "pattern_version_id", sa.Uuid(), sa.ForeignKey("pattern_versions.id"), nullable=False
        ),
        sa.Column("step_id", sa.Uuid(), sa.ForeignKey("steps.id"), nullable=False),
        sa.Column("relation", sa.String(32), nullable=False, server_default="REALIZES_STEP"),
        sa.UniqueConstraint(
            "pattern_version_id", "step_id", "relation", name="uq_pattern_version_step_relation"
        ),
    )
    op.create_index("ix_pattern_version_steps_step_id", "pattern_version_steps", ["step_id"])
    op.create_table(
        "phrase_usage_profiles",
        *_base(),
        sa.Column(
            "pattern_version_id", sa.Uuid(), sa.ForeignKey("pattern_versions.id"), nullable=False
        ),
        sa.Column("section_id", sa.Uuid(), sa.ForeignKey("sections.id")),
        sa.Column("genre_code", sa.String(64)),
        sa.Column("language_code", sa.String(16), nullable=False, server_default="en"),
        sa.Column("register_code", sa.String(64)),
        sa.Column("register_version", sa.String(32)),
        sa.Column("discipline_code", sa.String(128)),
        sa.Column("audience", sa.String(128)),
        sa.Column("preferred_usage", sa.String(32)),
    )
    op.create_index(
        "ix_phrase_usage_profiles_version_id", "phrase_usage_profiles", ["pattern_version_id"]
    )
    op.create_index("ix_phrase_usage_profiles_section_id", "phrase_usage_profiles", ["section_id"])
    op.create_index(
        "ix_phrase_usage_profiles_discipline_code", "phrase_usage_profiles", ["discipline_code"]
    )
    op.create_table(
        "pattern_version_pragmatic_tags",
        *_base(),
        sa.Column(
            "pattern_version_id", sa.Uuid(), sa.ForeignKey("pattern_versions.id"), nullable=False
        ),
        sa.Column(
            "feature_id", sa.Uuid(), sa.ForeignKey("apb_pragmatic_features.id"), nullable=False
        ),
        sa.Column("strength_note", sa.Text()),
        sa.Column("context_note", sa.Text()),
        sa.UniqueConstraint(
            "pattern_version_id", "feature_id", name="uq_pattern_version_pragmatic_feature"
        ),
    )
    op.create_index(
        "ix_pattern_version_pragmatic_tags_feature_id",
        "pattern_version_pragmatic_tags",
        ["feature_id"],
    )
    op.create_table(
        "phrase_examples",
        *_base(),
        sa.Column(
            "pattern_version_id", sa.Uuid(), sa.ForeignKey("pattern_versions.id"), nullable=False
        ),
        sa.Column("example_kind", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("origin_kind", sa.String(32), nullable=False, server_default="internal_original"),
        sa.Column("source_ref", sa.Text()),
        sa.Column("license_id", sa.Uuid(), sa.ForeignKey("licenses.id")),
        sa.CheckConstraint(
            "example_kind IN ('positive', 'negative', 'revised')", name="ck_apb_phrase_example_kind"
        ),
        sa.CheckConstraint(
            "origin_kind IN ('internal_original', 'illustrative_synthetic', 'licensed')",
            name="ck_apb_phrase_example_origin",
        ),
    )
    op.create_index("ix_phrase_examples_version_id", "phrase_examples", ["pattern_version_id"])
    op.create_table(
        "phrase_caveats",
        *_base(),
        sa.Column(
            "pattern_version_id", sa.Uuid(), sa.ForeignKey("pattern_versions.id"), nullable=False
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
    )
    op.create_index("ix_phrase_caveats_version_id", "phrase_caveats", ["pattern_version_id"])


def downgrade() -> None:
    for table, index in (
        ("phrase_caveats", "ix_phrase_caveats_version_id"),
        ("phrase_examples", "ix_phrase_examples_version_id"),
        ("pattern_version_pragmatic_tags", "ix_pattern_version_pragmatic_tags_feature_id"),
        ("phrase_usage_profiles", "ix_phrase_usage_profiles_discipline_code"),
        ("phrase_usage_profiles", "ix_phrase_usage_profiles_section_id"),
        ("phrase_usage_profiles", "ix_phrase_usage_profiles_version_id"),
        ("pattern_version_steps", "ix_pattern_version_steps_step_id"),
        ("pattern_version_moves", "ix_pattern_version_moves_move_id"),
        ("pattern_version_functions", "ix_pattern_version_functions_function_id"),
        ("apb_communicative_functions", "ix_apb_communicative_functions_family_id"),
    ):
        op.drop_index(index, table_name=table)
    for table in (
        "phrase_caveats",
        "phrase_examples",
        "pattern_version_pragmatic_tags",
        "phrase_usage_profiles",
        "pattern_version_steps",
        "pattern_version_moves",
        "pattern_version_functions",
        "apb_pragmatic_features",
        "apb_communicative_functions",
        "apb_function_families",
    ):
        op.drop_table(table)
