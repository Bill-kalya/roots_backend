"""Merge heads a1c2b3d4e5f6 and add_testimonials_table

Revision ID: merge_a1c2b3d4e5f6_add_testimonials
Revises: a1c2b3d4e5f6, add_testimonials_table
Create Date: 2026-06-23 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'merge_a1c2b3d4e5f6_add_testimonials'
down_revision = ('a1c2b3d4e5f6', 'add_testimonials_table')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge-only migration: no DB changes required.
    pass


def downgrade() -> None:
    # Nothing to do here for merge-only revision
    pass
