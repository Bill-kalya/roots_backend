"""merge_heads

Revision ID: 02ac92b60e7c
Revises: 08c5f024b43a, a1_chat_conversations_messages
Create Date: 2026-06-06 10:29:30.523299

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '02ac92b60e7c'
down_revision = ('08c5f024b43a', 'a1_chat_conversations_messages')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

