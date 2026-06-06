"""create shipping_zones table

Revision ID: zz_shipping_zones_phase1
Revises: f64c3e7ae9d2
Create Date: 2026-05-31

"""

from alembic import op
import sqlalchemy as sa

revision = 'zz_shipping_zones_phase1'
down_revision = 'f64c3e7ae9d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'shipping_zones',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('country_code', sa.String(length=2), nullable=False, unique=True),
        sa.Column('base_rate', sa.Numeric(10,2), nullable=False),
        sa.Column('per_kg_rate', sa.Numeric(10,2), nullable=False),
    )

    # Seed Phase-1 sample zones (safe for dev; ignores duplicates in many DBs)
    op.execute("""
        INSERT INTO shipping_zones (country_code, base_rate, per_kg_rate)
        VALUES
            ('US', 25, 8),
            ('CA', 30, 9),
            ('UK', 22, 7),
            ('AE', 20, 6)
        ON CONFLICT (country_code) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table('shipping_zones')

