"""Add case-insensitive unique index on lower(email)

Revision ID: a1c2b3d4e5f6
Revises: zz_shipping_zones_phase1
Create Date: 2026-06-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1c2b3d4e5f6'
down_revision = 'zz_shipping_zones_phase1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Drop existing unique constraint/index on users.email if present
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")
    op.execute("DROP INDEX IF EXISTS ix_users_email")

    # 2) Normalize emails to lowercase
    op.execute("UPDATE users SET email = lower(email) WHERE email IS NOT NULL")

    # 3) Ensure there are no duplicates when lowercased; fail early with clear message if there are
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (
        SELECT lower(email) FROM users WHERE email IS NOT NULL GROUP BY lower(email) HAVING count(*) > 1
      ) THEN
        RAISE EXCEPTION 'Migration a1c2b3d4e5f6 aborted: duplicate emails detected when lowercasing. Resolve duplicates manually before re-running this migration.';
      END IF;
    END$$;
    """)

    # 4) Create a case-insensitive unique index on lower(email)
    # Use a standard CREATE INDEX (not CONCURRENTLY) because Alembic migration runs in a transaction by default.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_lower_unique ON users (lower(email))")


def downgrade() -> None:
    # Drop the case-insensitive unique index
    op.execute("DROP INDEX IF EXISTS ix_users_email_lower_unique")

    # Recreate the original unique constraint on email (note: this will fail if duplicates exist)
    op.execute("ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email)")
