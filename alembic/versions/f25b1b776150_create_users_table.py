"""create users table

Revision ID: f25b1b776150
Revises: 
Create Date: 2026-04-21 18:44:50.355149

Minimal users table creation - role added in next migration.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f25b1b776150'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('users',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255)),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('is_verified', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('merchant_approved', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('merchant_details', sa.JSON(), nullable=True),
        sa.Column('store_name', sa.String(255), nullable=True),
        sa.Column('store_description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

def downgrade() -> None:
    op.drop_table('users')

