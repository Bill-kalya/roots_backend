"""add audit_logs table

Revision ID: df49334632a0
Revises: 831669f74097
Create Date: 2026-05-07 20:16:29.079845

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'df49334632a0'
down_revision = '831669f74097'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("idx_audit_user_action", "audit_logs", ["user_id", "action"])
    op.create_index("idx_audit_created_at", "audit_logs", ["created_at"])
    op.create_index("idx_audit_resource", "audit_logs", ["resource", "resource_id"])



def downgrade() -> None:
    op.drop_index("idx_audit_resource", table_name="audit_logs")
    op.drop_index("idx_audit_created_at", table_name="audit_logs")
    op.drop_index("idx_audit_user_action", table_name="audit_logs")
    op.drop_table("audit_logs")


