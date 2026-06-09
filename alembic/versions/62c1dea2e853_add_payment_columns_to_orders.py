"""add_payment_columns_to_orders

Revision ID: 62c1dea2e853
Revises: 13b29a22f72c
Create Date: 2026-05-22 09:26:29.301376

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '62c1dea2e853'
down_revision = '13b29a22f72c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This migration duplicates payment columns that were already added in
    # revision 13b29a22f72c. Keep this upgrade non-destructive.
    pass






def downgrade() -> None:
    # Downgrade intentionally does nothing.
    # This prevents dropping payment columns or recreating audit_logs during rollback.
    pass


