"""add merchant_wallets, transaction_ledger, payouts tables

Revision ID: zz_wallet_escrow_phase1
Revises: a6f6154ec010
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision = "zz_wallet_escrow_phase1"
down_revision = "baseline_20260703"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # merchant_wallets
    op.create_table(
        "merchant_wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), unique=True, nullable=False, index=True),
        sa.Column("available_balance", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("pending_balance", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("total_earned", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("total_withdrawn", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'KES'")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_merchant_wallets_merchant_id", "merchant_wallets", ["merchant_id"])

    # transaction_ledger
    op.create_table(
        "transaction_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchant_wallets.id"), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("entry_type", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'KES'")),
        sa.Column("reference_id", sa.String(255), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_ledger_merchant_id", "transaction_ledger", ["merchant_id"])
    op.create_index("idx_ledger_created_at", "transaction_ledger", ["created_at"])

    # payouts
    op.create_table(
        "payouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'KES'")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("payout_method", sa.String(30), nullable=True),
        sa.Column("recipient_detail", sa.String(255), nullable=True),
        sa.Column("mpesa_conversation_id", sa.String(255), nullable=True),
        sa.Column("mpesa_receipt", sa.String(100), nullable=True),
        sa.Column("provider_payout_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_payouts_merchant_id", "payouts", ["merchant_id"])
    op.create_index("idx_payouts_status", "payouts", ["status"])


def downgrade() -> None:
    op.drop_table("payouts")
    op.drop_table("transaction_ledger")
    op.drop_table("merchant_wallets")
