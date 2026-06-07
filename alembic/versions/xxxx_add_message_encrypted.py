"""add message encrypted column

Revision ID: xxxx
Revises: a1_chat_conversations_messages
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b6c8e0f0d1"
down_revision = "a1_chat_conversations_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "encrypted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "encrypted")

