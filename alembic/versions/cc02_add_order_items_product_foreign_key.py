"""add order_items product foreign key

Revision ID: cc02_add_order_items_product_foreign_key
Revises: 4e8c88804689
Create Date: 2026-06-09

"""

from alembic import op


revision = 'cc02'
down_revision = '4e8c88804689'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        'fk_order_items_product_id_products',
        'order_items',
        'products',
        ['product_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_order_items_product_id_products',
        'order_items',
        type_='foreignkey',
    )

