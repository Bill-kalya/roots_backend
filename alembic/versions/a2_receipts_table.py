from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "a2_receipts_table"
down_revision = "baseline_initial_schema_real"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "receipts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "order_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("payment_reference", sa.String(255), nullable=False),
        sa.Column("payment_method", sa.String(20), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("canonical_hash", sa.String(64), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("shipping_fee", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="KES"),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="paid"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),

        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_receipts_order_id_orders",
            ondelete="RESTRICT",
        ),
    )

    op.create_index("ix_receipts_order_id", "receipts", ["order_id"])
    op.create_index("ix_receipts_customer_email", "receipts", ["customer_email"])
    op.create_index("ix_receipts_canonical_hash", "receipts", ["canonical_hash"])

    op.create_index(
        "uq_receipts_payment_reference",
        "receipts",
        ["payment_reference"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_receipts_canonical_hash", table_name="receipts")
    op.drop_index("ix_receipts_customer_email", table_name="receipts")
    op.drop_index("ix_receipts_order_id", table_name="receipts")
    op.drop_index("uq_receipts_payment_reference", table_name="receipts")
    op.drop_table("receipts")

