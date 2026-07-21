"""fix gallery and materials: NOT NULL + server_default []

Revision ID: 85f788c0c91a
Revises: 7ac2ebefde08
Create Date: 2026-07-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '85f788c0c91a'
down_revision = '7ac2ebefde08'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill NULL values to empty arrays before adding NOT NULL
    op.execute("UPDATE products SET gallery = '{}' WHERE gallery IS NULL")
    op.execute("UPDATE products SET materials = '{}' WHERE materials IS NULL")

    op.alter_column(
        "products",
        "gallery",
        existing_type=postgresql.ARRAY(sa.Text()),
        server_default=sa.text("'{}'::text[]"),
        nullable=False,
    )
    op.alter_column(
        "products",
        "materials",
        existing_type=postgresql.ARRAY(sa.Text()),
        server_default=sa.text("'{}'::text[]"),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "products",
        "materials",
        existing_type=postgresql.ARRAY(sa.Text()),
        server_default=None,
        nullable=True,
    )
    op.alter_column(
        "products",
        "gallery",
        existing_type=postgresql.ARRAY(sa.Text()),
        server_default=None,
        nullable=True,
    )
