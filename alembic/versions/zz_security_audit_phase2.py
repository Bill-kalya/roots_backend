"""security: non-negative balance constraints, ledger actor_id/ip_address

Adds CHECK constraints to prevent negative balances, adds actor_id and
ip_address columns to transaction_ledger for audit trail, and merges
the two migration heads (add_testimonials_table, zz_wallet_escrow_phase1)
into a single lineage.

Revision ID: zz_security_audit_phase2
Revises: add_testimonials_table, zz_wallet_escrow_phase1
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "zz_security_audit_phase2"
down_revision = ("add_testimonials_table", "zz_wallet_escrow_phase1")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Non-negative balance CHECK constraints on merchant_wallets
    op.create_check_constraint(
        "ck_merchant_wallets_available_balance_ge_zero",
        "merchant_wallets",
        sa.sql.column("available_balance") >= 0,
    )
    op.create_check_constraint(
        "ck_merchant_wallets_pending_balance_ge_zero",
        "merchant_wallets",
        sa.sql.column("pending_balance") >= 0,
    )

    # Actor/IP columns on transaction_ledger
    op.add_column(
        "transaction_ledger",
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "transaction_ledger",
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index("idx_ledger_actor_id", "transaction_ledger", ["actor_id"])


def downgrade() -> None:
    op.drop_index("idx_ledger_actor_id", table_name="transaction_ledger")
    op.drop_column("transaction_ledger", "ip_address")
    op.drop_column("transaction_ledger", "actor_id")
    op.drop_constraint("ck_merchant_wallets_available_balance_ge_zero", "merchant_wallets")
    op.drop_constraint("ck_merchant_wallets_pending_balance_ge_zero", "merchant_wallets")
