"""merge heads

Revision ID: 4e8c88804689
Revises: d9bee3d56f04, a1b6c8e0f0d1
Create Date: 2026-06-07 15:27:26.107933

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4e8c88804689'
down_revision = ('d9bee3d56f04', 'a1b6c8e0f0d1')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

