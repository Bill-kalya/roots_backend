"""create_products_table_actual

Revision ID: ac10e4f9b2d3
Revises: 62c1dea2e853
Create Date: 2026-06-09 20:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ac10e4f9b2d3'
down_revision = '62c1dea2e853'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'products',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('long_description', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('origin', sa.String(length=100), nullable=False),
        sa.Column('tag', sa.String(length=100), nullable=True),
        sa.Column('stock', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('is_featured', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('products')
