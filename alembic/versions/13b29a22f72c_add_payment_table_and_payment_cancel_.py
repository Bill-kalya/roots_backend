"""add payment table and payment/cancel fields to orders

Revision ID: 13b29a22f72c
Revises: 16f74fa27da4
Create Date: 2026-05-22 08:12:22.055599

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '13b29a22f72c'
down_revision = 'cc01_create_orders_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Create payments table (non-destructive)
    if not inspector.has_table('payments'):
        op.create_table(
            'payments',
            sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('order_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, unique=True),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('provider_transaction_id', sa.String(length=255), nullable=True, unique=True),
            sa.Column('status', sa.Enum('pending', 'completed', 'failed', 'cancelled', name='paymentstatus'), nullable=False, server_default='pending'),
            sa.Column('amount', sa.Numeric(10, 2), nullable=False),
            sa.Column('currency', sa.String(length=10), nullable=False, server_default='KES'),
            sa.Column('raw_payload', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            # TimestampMixin fields in this codebase: created_at, updated_at
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_payments_order_id_orders')),
        )

    # Extend orders with payment/cancel fields (idempotent)
    if inspector.has_table('orders'):
        existing_cols = {c['name'] for c in inspector.get_columns('orders')}

        if 'payment_provider' not in existing_cols:
            op.add_column('orders', sa.Column('payment_provider', sa.String(length=50), nullable=True))
        if 'payment_reference' not in existing_cols:
            op.add_column('orders', sa.Column('payment_reference', sa.String(length=255), nullable=True))
        if 'paid_at' not in existing_cols:
            op.add_column('orders', sa.Column('paid_at', sa.DateTime(), nullable=True))
        if 'cancelled_at' not in existing_cols:
            op.add_column('orders', sa.Column('cancelled_at', sa.DateTime(), nullable=True))
        if 'cancellation_reason' not in existing_cols:
            op.add_column('orders', sa.Column('cancellation_reason', sa.String(length=255), nullable=True))




def downgrade() -> None:
    pass

