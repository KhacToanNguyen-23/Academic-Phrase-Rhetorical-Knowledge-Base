"""Merge measurement catalog and dev migration heads.

Revision ID: 0018_merge_measurement_and_dev
Revises: 0016_measurement_catalog, 0017_merge_auth_and_vocab
Create Date: 2026-11-09
"""

revision = "0018_merge_measurement_and_dev"
down_revision = ("0016_measurement_catalog", "0017_merge_auth_and_vocab")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
