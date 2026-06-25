"""restore trusted_devices column

Revision ID: a6f6154ec010
Revises: merchant_payout_settings_003
Create Date: 2026-06-26 01:39:51.511448

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a6f6154ec010'
down_revision = 'merchant_payout_settings_003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "trusted_devices",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "trusted_devices")


