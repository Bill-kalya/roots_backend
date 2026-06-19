"""add stripe_webhook_events table for webhook idempotency

Revision ID: add_stripe_webhook_events
Revises: 13b29a22f72c
Create Date: 2026-06-15

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_stripe_webhook_events"
down_revision = "13b29a22f72c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("stripe_webhook_events"):
        op.create_table(
            "stripe_webhook_events",
            sa.Column(
                "id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("event_id", sa.String(length=255), nullable=False, unique=True),
            sa.Column("event_type", sa.String(length=255), nullable=False),
            sa.Column(
                "processed_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
        )
    else:
        # Table exists; do nothing.
        pass


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("stripe_webhook_events"):
        op.drop_table("stripe_webhook_events")

