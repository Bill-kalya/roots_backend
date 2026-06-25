from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = "merchant_payout_settings_001"
down_revision = "3b7c5c7d9f42"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "merchant_payout_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payout_method", sa.String(length=30), nullable=False),
        sa.Column("mpesa_phone", sa.String(length=20), nullable=True),
        sa.Column("paypal_email", sa.String(length=255), nullable=True),
        sa.Column("stripe_account_id", sa.String(length=255), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("merchant_id"),
    )
    op.create_index(
        "idx_merchant_payout_settings_merchant_id",
        "merchant_payout_settings",
        ["merchant_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("idx_merchant_payout_settings_merchant_id", table_name="merchant_payout_settings")
    op.drop_table("merchant_payout_settings")

