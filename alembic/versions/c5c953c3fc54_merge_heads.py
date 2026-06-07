"""merge_heads

Revision ID: c5c953c3fc54
Revises: 02ac92b60e7c, 16f74fa27da4, 9670021d2cf1
Create Date: 2026-06-07 04:07:58.293783

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5c953c3fc54'
down_revision = ('02ac92b60e7c', '16f74fa27da4', '9670021d2cf1')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

