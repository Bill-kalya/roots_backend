"""create payments table with mpesa fields

Revision ID: a1b2c3d4e5f6
Revises: 38c7f89dbb56
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "38c7f89dbb56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # asyncpg requires one statement per op.execute() call.

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE paymentstatus AS ENUM (
                'pending', 'completed', 'failed', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id                      UUID          PRIMARY KEY,
            order_id                UUID          REFERENCES orders(id),
            provider                VARCHAR(50)   NOT NULL,
            provider_transaction_id VARCHAR(255)  UNIQUE,
            status                  paymentstatus NOT NULL DEFAULT 'pending',
            amount                  NUMERIC(10,2) NOT NULL,
            currency                VARCHAR(10)   NOT NULL DEFAULT 'KES',
            phone                   VARCHAR(20),
            checkout_request_id     VARCHAR(255)  UNIQUE,
            mpesa_receipt           VARCHAR(100),
            result_code             VARCHAR(10),
            raw_payload             TEXT,
            created_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_payments_order_id
            ON payments (order_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_payments_status
            ON payments (status)
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_checkout_request_id
            ON payments (checkout_request_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payments")
    op.execute("DROP TYPE IF EXISTS paymentstatus")
