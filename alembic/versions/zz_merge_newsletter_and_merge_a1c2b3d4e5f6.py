"""Merge heads for newsletter_subscribers and resolve multi-head Alembic state.

Revision ID: 3b7c5c7d9f42
Revises: 4f6b0f4e2b1a, merge_a1c2b3d4e5f6
Create Date: 2026-06-23

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "3b7c5c7d9f42"
down_revision = ("4f6b0f4e2b1a", "merge_a1c2b3d4e5f6")
branch_labels = None
depends_on = None


def upgrade():
    """No-op merge revision (connects two heads)."""
    pass


def downgrade():
    """No-op downgrade for merge revision."""
    pass

