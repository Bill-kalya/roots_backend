"""add mpesa till number support

Revision ID: merchant_payout_settings_002
Revises: merchant_payout_settings_001
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa

revision = "merchant_payout_settings_002"
down_revision = "merchant_payout_settings_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merchant_payout_settings",
        sa.Column(
            "mpesa_mode",
            sa.String(length=10),
            nullable=False,
            server_default="PHONE",
        ),
    )
    op.add_column(
        "merchant_payout_settings",
        sa.Column("mpesa_till_number", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("merchant_payout_settings", "mpesa_till_number")
    op.drop_column("merchant_payout_settings", "mpesa_mode")

