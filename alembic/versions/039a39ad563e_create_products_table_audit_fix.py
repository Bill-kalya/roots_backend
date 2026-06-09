"""create products table (audit fix)

Revision ID: 039a39ad563e
Revises: cc02_add_order_items_product_foreign_key
Create Date: 2026-06-09 16:08:09.312210

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '039a39ad563e'
down_revision = 'cc02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create products table if missing and ensure required columns/FK/index exist.
    # This migration is intentionally idempotent because Railway builds from migrations only.

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY,
            merchant_id UUID,

            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            long_description TEXT,
            price NUMERIC(10,2) NOT NULL,
            image_url VARCHAR(500) NOT NULL,

            gallery TEXT[],
            origin VARCHAR(100) NOT NULL,
            tag VARCHAR(100),
            stock INTEGER DEFAULT 0 NOT NULL,

            is_featured BOOLEAN DEFAULT FALSE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE NOT NULL,

            artisan VARCHAR(255),
            weight VARCHAR(100),
            dimensions VARCHAR(100),
            year INTEGER,
            materials TEXT[],

            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """
    )

    # Add merchant FK if missing
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'products_merchant_id_fkey'
            ) THEN
                ALTER TABLE products
                ADD CONSTRAINT products_merchant_id_fkey
                FOREIGN KEY (merchant_id) REFERENCES users(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )

    # Ensure index exists
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_products_merchant_id
        ON products(merchant_id);
        """
    )

    # Ensure later migrations' columns exist (safe if already present)
    for col, ddl in [
        ('gallery', 'gallery TEXT[]'),
        ('artisan', 'artisan VARCHAR(255)'),
        ('weight', 'weight VARCHAR(100)'),
        ('dimensions', 'dimensions VARCHAR(100)'),
        ('year', 'year INTEGER'),
        ('materials', 'materials TEXT[]'),
    ]:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema='public'
                      AND table_name='products'
                      AND column_name='{col}'
                ) THEN
                    ALTER TABLE products ADD COLUMN {ddl};
                END IF;
            END $$;
            """
        )



def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_products_merchant_id;")
    op.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS products_merchant_id_fkey;")
    op.execute("DROP TABLE IF EXISTS products;")


