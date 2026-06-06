"""chat conversations and messages

Revision ID: a1_chat_conversations_messages
Revises: 
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
import datetime

# revision identifiers, used by Alembic.
revision = 'a1_chat_conversations_messages'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('room_id', sa.String(length=200), nullable=False),
        sa.Column('type', sa.Enum('DIRECT', name='conversationtype', create_type=False), nullable=False, server_default='DIRECT'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('customer_id', 'merchant_id', name='uq_conversation_customer_merchant'),
        sa.UniqueConstraint('room_id', name='uq_conversation_room_id'),
    )
    # index
    op.create_index('ix_conversations_room_id', 'conversations', ['room_id'], unique=False)

    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='delivered'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_messages_conversation_created_at', 'messages', ['conversation_id', 'created_at'], unique=False)


def downgrade():
    op.drop_index('ix_messages_conversation_created_at', table_name='messages')
    op.drop_table('messages')

    op.drop_index('ix_conversations_room_id', table_name='conversations')
    op.drop_table('conversations')

