"""add pochi phone to support POCHI la biashara

Revision ID: merchant_payout_settings_003
Revises: merchant_payout_settings_002
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa

revision = "merchant_payout_settings_003"
down_revision = "merchant_payout_settings_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merchant_payout_settings",
        sa.Column("pochi_phone", sa.String(length=15), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("merchant_payout_settings", "pochi_phone")

