"""paypal: add KES/USD conversion fields, payer_id, refunded status

Revision ID: a4b7c9d1e2f3
Revises: 9f1a6e2b7c4d
Create Date: 2026-08-04

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a4b7c9d1e2f3'
down_revision = '9f1a6e2b7c4d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------------
    # 1. New enum value for refunds (ALTER TYPE ADD VALUE cannot run inside
    #    a transaction block, so use an autocommit block).
    # ---------------------------------------------------------------------
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'refunded'")

    # ---------------------------------------------------------------------
    # 2. PayPal currency conversion + payer tracking columns
    # ---------------------------------------------------------------------
    op.add_column('payments', sa.Column('amount_kes', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('payments', sa.Column('amount_usd', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('payments', sa.Column('exchange_rate', sa.Numeric(precision=12, scale=6), nullable=True))
    op.add_column('payments', sa.Column('payer_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('payments', 'payer_id')
    op.drop_column('payments', 'exchange_rate')
    op.drop_column('payments', 'amount_usd')
    op.drop_column('payments', 'amount_kes')

    # Remove the 'refunded' enum value (recreate type without it).
    op.execute("ALTER TABLE payments ALTER COLUMN status TYPE varchar(20) USING status::varchar")
    op.execute("DROP TYPE paymentstatus")
    op.execute(
        "CREATE TYPE paymentstatus AS ENUM ('pending', 'completed', 'failed', 'cancelled')"
    )
    op.execute("ALTER TABLE payments ALTER COLUMN status TYPE paymentstatus USING status::paymentstatus")
