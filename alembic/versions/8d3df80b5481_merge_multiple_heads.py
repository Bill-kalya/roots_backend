"""merge_multiple_heads

Revision ID: 8d3df80b5481
Revises: a2_receipts_table, merchant_payout_settings_001, add_stripe_webhook_events
Create Date: 2026-06-17 11:53:19.295645

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8d3df80b5481'
down_revision = ('a2_receipts_table', 'merchant_payout_settings_001', 'add_stripe_webhook_events')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

