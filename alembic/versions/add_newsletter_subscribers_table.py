"""add newsletter_subscribers table

Revision ID: 4f6b0f4e2b1a
Revises: 9f9584b0c458
Create Date: 2026-06-23

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "4f6b0f4e2b1a"
down_revision = "9f9584b0c458"
branch_labels = None
depends_on = None


def upgrade():
    # This table might already exist in some environments (e.g. manual creation or
    # a previously generated migration applied). Make the migration idempotent.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'newsletter_subscribers'
            ) THEN
                CREATE TABLE newsletter_subscribers (
                    id UUID NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    is_confirmed BOOLEAN DEFAULT false NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
                    PRIMARY KEY (id),
                    UNIQUE (email)
                );
            END IF;
        END $$;
        """
    )

    # Ensure index exists (harmless if already present)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_newsletter_subscribers_email
        ON newsletter_subscribers (email);
        """
    )



def downgrade():
    op.drop_index("ix_newsletter_subscribers_email", table_name="newsletter_subscribers")
    op.drop_table("newsletter_subscribers")

