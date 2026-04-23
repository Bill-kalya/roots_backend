"""Add role column and merchant fields to users table

Revision ID: 0001
Revises: 
Create Date: 2024

Equivalent to add_role_column() script
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = 'f25b1b776150'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type if not exists (idempotent)
    enum_create = """
    DO $$ BEGIN
        CREATE TYPE userrole AS ENUM ('USER', 'MERCHANT', 'ADMIN');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """
    op.execute(enum_create)
    
    # Add role column if not exists
    op.execute("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS role userrole DEFAULT 'USER'
    """)
    
    # Add merchant fields if not exists
    op.execute("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS merchant_approved BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS merchant_details JSONB,
        ADD COLUMN IF NOT EXISTS store_name VARCHAR(255),
        ADD COLUMN IF NOT EXISTS store_description TEXT
    """)
    
    # Update admin user role (if exists)
    op.execute("""
        UPDATE users 
        SET role = 'ADMIN' 
        WHERE email = 'admin@roots.com'
    """)


def downgrade() -> None:
    # Drop columns if exist
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS store_description")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS store_name")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS merchant_details")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS merchant_approved")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS role")
    
    # Drop enum type if no dependencies
    op.execute("""
        DROP TYPE IF EXISTS userrole CASCADE
    """)

