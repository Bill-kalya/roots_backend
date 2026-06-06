"""merge_heads

Revision ID: 08c5f024b43a
Revises: 88a2fc43b0f8, zz_shipping_zones_phase1
Create Date: 2026-06-01 19:22:03.075031

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '08c5f024b43a'
down_revision = ('88a2fc43b0f8', 'zz_shipping_zones_phase1')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

