"""baseline: pre-wallet schema snapshot

This is a no-op baseline migration that marks the current production
schema state before wallet/escrow migrations. All tables and constraints
already exist in production at this point.

Revision ID: baseline_20260703
Revises: None (baseline)
Create Date: 2026-07-03

"""
from alembic import op

revision = "baseline_20260703"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op baseline - production schema already exists
    pass


def downgrade() -> None:
    # No-op baseline - production schema already exists
    pass