"""create orders and order_items tables

Revision ID: cc01_create_orders_table
Revises: 831669f74097
Create Date: 2026-06-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'cc01_create_orders_table'
down_revision = '831669f74097'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'orders',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum(
            'pending', 'paid', 'shipped', 'delivered', 'cancelled',
            name='orderstatus'
        ), nullable=True, server_default='pending'),
        sa.Column('subtotal', sa.Numeric(10, 2), nullable=False),
        sa.Column('shipping_fee', sa.Numeric(10, 2), nullable=True, server_default='0'),
        sa.Column('total', sa.Numeric(10, 2), nullable=False),
        sa.Column('payment_provider', sa.String(50), nullable=True),
        sa.Column('payment_reference', sa.String(255), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancellation_reason', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_orders_user_id_users'),
    )

    op.create_table(
        'order_items',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('order_id', UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name_snapshot', sa.String(255), nullable=False),
        sa.Column('price_snapshot', sa.Numeric(10, 2), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name='fk_order_items_order_id_orders'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], name='fk_order_items_product_id_products'),
    )


def downgrade() -> None:
    op.drop_table('order_items')
    op.drop_table('orders')
    op.execute("DROP TYPE IF EXISTS orderstatus")

