"""normalize: drop stale wallet tables, convert payment/message statuses to enums

Revision ID: 9f1a6e2b7c4d
Revises: 85f788c0c91a
Create Date: 2026-08-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9f1a6e2b7c4d'
down_revision = '85f788c0c91a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------------
    # 1. Drop stale wallet/escrow/payout tables (removed in direct-settlement
    #    refactor). transaction_ledger references merchant_wallets, so drop
    #    it first.
    # ---------------------------------------------------------------------
    op.drop_table('transaction_ledger')
    op.drop_table('payouts')
    op.drop_table('merchant_wallets')
    op.drop_table('merchant_payout_settings')

    # ---------------------------------------------------------------------
    # 2. Convert payments.provider -> paymentprovider enum
    # ---------------------------------------------------------------------
    op.execute("CREATE TYPE paymentprovider AS ENUM ('mpesa', 'stripe', 'paypal')")
    op.execute(
        "ALTER TABLE payments ALTER COLUMN provider "
        "TYPE paymentprovider USING provider::paymentprovider"
    )

    # ---------------------------------------------------------------------
    # 3. Convert payments.status -> paymentstatus enum
    # ---------------------------------------------------------------------
    op.execute("CREATE TYPE paymentstatus AS ENUM ('pending', 'completed', 'failed', 'cancelled')")
    op.execute(
        "ALTER TABLE payments ALTER COLUMN status "
        "TYPE paymentstatus USING status::paymentstatus"
    )

    # ---------------------------------------------------------------------
    # 4. Convert messages.status -> messagestatus enum
    # ---------------------------------------------------------------------
    op.execute("CREATE TYPE messagestatus AS ENUM ('sent', 'delivered', 'read')")
    op.execute(
        "ALTER TABLE messages ALTER COLUMN status "
        "TYPE messagestatus USING status::messagestatus"
    )


def downgrade() -> None:
    # ---------------------------------------------------------------------
    # Revert enum columns back to plain strings
    # ---------------------------------------------------------------------
    op.execute("ALTER TABLE messages ALTER COLUMN status TYPE varchar(20)")
    op.execute("DROP TYPE messagestatus")

    op.execute("ALTER TABLE payments ALTER COLUMN status TYPE varchar(20)")
    op.execute("DROP TYPE paymentstatus")

    op.execute("ALTER TABLE payments ALTER COLUMN provider TYPE varchar(50)")
    op.execute("DROP TYPE paymentprovider")

    # ---------------------------------------------------------------------
    # Recreate dropped tables (from initial_schema)
    # ---------------------------------------------------------------------
    op.create_table(
        'merchant_payout_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('merchant_id', sa.UUID(), nullable=False),
        sa.Column('payout_method', sa.String(length=30), nullable=False),
        sa.Column('mpesa_phone', sa.String(length=20), nullable=True),
        sa.Column('mpesa_mode', sa.String(length=10), server_default='PHONE', nullable=False),
        sa.Column('mpesa_till_number', sa.String(length=20), nullable=True),
        sa.Column('pochi_phone', sa.String(length=15), nullable=True),
        sa.Column('paypal_email', sa.String(length=255), nullable=True),
        sa.Column('stripe_account_id', sa.String(length=255), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_merchant_payout_settings_merchant_id', 'merchant_payout_settings', ['merchant_id'], unique=True)

    op.create_table(
        'merchant_wallets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('merchant_id', sa.UUID(), nullable=False),
        sa.Column('available_balance', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('pending_balance', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('total_earned', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('total_withdrawn', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_merchant_wallets_merchant_id', 'merchant_wallets', ['merchant_id'], unique=True)

    op.create_table(
        'payouts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('merchant_id', sa.UUID(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('payout_method', sa.String(length=30), nullable=True),
        sa.Column('recipient_detail', sa.String(length=255), nullable=True),
        sa.Column('mpesa_conversation_id', sa.String(length=255), nullable=True),
        sa.Column('mpesa_receipt', sa.String(length=100), nullable=True),
        sa.Column('provider_payout_id', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['merchant_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_payouts_merchant_id', 'payouts', ['merchant_id'], unique=False)
    op.create_index('idx_payouts_status', 'payouts', ['status'], unique=False)

    op.create_table(
        'transaction_ledger',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('merchant_id', sa.UUID(), nullable=False),
        sa.Column('wallet_id', sa.UUID(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('entry_type', sa.String(length=20), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('reference_id', sa.String(length=255), nullable=True),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('actor_id', sa.UUID(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.ForeignKeyConstraint(['merchant_id'], ['users.id']),
        sa.ForeignKeyConstraint(['wallet_id'], ['merchant_wallets.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_ledger_actor_id', 'transaction_ledger', ['actor_id'], unique=False)
    op.create_index('idx_ledger_created_at', 'transaction_ledger', ['created_at'], unique=False)
    op.create_index('idx_ledger_merchant_id', 'transaction_ledger', ['merchant_id'], unique=False)
