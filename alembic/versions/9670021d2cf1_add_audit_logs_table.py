"""add audit_logs table

Revision ID: 9670021d2cf1
Revises: df49334632a0
Create Date: 2026-05-07 20:20:53.241964

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9670021d2cf1'
down_revision = 'df49334632a0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This revision also targets audit_logs.
    # Keep it idempotent-safe by creating the table only if it doesn't exist.
    # Alembic doesn't provide native IF NOT EXISTS for create_table, so use raw SQL.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID PRIMARY KEY,
            user_id UUID NULL,
            action VARCHAR(100) NOT NULL,
            resource VARCHAR(100) NOT NULL,
            resource_id VARCHAR(255) NULL,
            details JSON NULL,
            ip_address VARCHAR(45) NULL,
            user_agent VARCHAR(500) NULL,
            status VARCHAR(20) NOT NULL,
            error_message VARCHAR(1000) NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        );
        """.strip()
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE tablename = 'audit_logs' AND indexname = 'idx_audit_user_action'
            ) THEN
                CREATE INDEX idx_audit_user_action ON audit_logs(user_id, action);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE tablename = 'audit_logs' AND indexname = 'idx_audit_created_at'
            ) THEN
                CREATE INDEX idx_audit_created_at ON audit_logs(created_at);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE tablename = 'audit_logs' AND indexname = 'idx_audit_resource'
            ) THEN
                CREATE INDEX idx_audit_resource ON audit_logs(resource, resource_id);
            END IF;
        END $$;
        """.strip()
    )



def downgrade() -> None:
    # Conservative downgrade: drop indexes and table
    op.execute("DROP INDEX IF EXISTS idx_audit_user_action;" )
    op.execute("DROP INDEX IF EXISTS idx_audit_created_at;" )
    op.execute("DROP INDEX IF EXISTS idx_audit_resource;" )
    op.execute("DROP TABLE IF EXISTS audit_logs;" )


