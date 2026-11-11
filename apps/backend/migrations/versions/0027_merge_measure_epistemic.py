"""Merge measurement and epistemic lexicon migration heads."""

revision: str = "0027_merge_measure_epistemic"
down_revision: tuple[str, str] = (
    "0023_merge_measure_links_labels",
    "0026_license_external_processing",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
