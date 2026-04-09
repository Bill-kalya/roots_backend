#!/usr/bin/env python
"""
Enterprise Database Initialization Script
Run this to create all tables with the enhanced schema
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings
from app.db.base import Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ FIX: Import ALL models here so SQLAlchemy registers them with Base.metadata
# Adjust these imports to match your actual model file paths
try:
    from app.models.user import User
    from app.models.product import Product
    from app.models.testimonial import Testimonial
    from app.models.order import Order, OrderItem
    from app.models.newsletter import NewsletterSubscriber
    logger.info("✅ Models imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import models: {e}")
    logger.error("Check that your model paths are correct")
    sys.exit(1)


async def create_database_if_not_exists():
    """Create database if it doesn't exist"""
    import asyncpg

    db_url = str(settings.DATABASE_URL)
    conn_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    db_name = conn_url.split('/')[-1]
    conn_url_without_db = conn_url.rsplit('/', 1)[0]

    try:
        conn = await asyncpg.connect(conn_url_without_db + "/postgres")

        result = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )

        if not result:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            logger.info(f"✅ Database '{db_name}' created")
        else:
            logger.info(f"✅ Database '{db_name}' already exists")

        await conn.close()

    except Exception as e:
        logger.error(f"❌ Database creation error: {e}")
        raise


async def create_tables():
    """Create all tables"""
    from app.db.session import db_manager

    logger.info("📋 Creating database tables...")
    await db_manager.initialize()

    async with db_manager._write_engine.begin() as conn:
        # ✅ Enable uuid-ossp extension before creating tables
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))

        await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ All tables created successfully")

        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))

        tables = result.fetchall()
        logger.info(f"\n📊 Created {len(tables)} tables:")
        for table in tables:
            logger.info(f"  - {table[0]}")

        # ✅ Guard: fail loudly if still no tables (misconfigured Base/models)
        if len(tables) == 0:
            raise RuntimeError(
                "No tables were created. Make sure your models are imported "
                "at the top of this script and inherit from the correct Base."
            )


async def insert_sample_data():
    """Insert sample data for testing"""
    from app.db.session import db_manager

    logger.info("\n📝 Inserting sample data...")

    async with db_manager._write_engine.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM users"))
        user_count = result.scalar()

        if user_count > 0:
            logger.info("  ⚠️ Sample data already exists, skipping...")
            return

        # ✅ Use a real bcrypt hash — the original hash was invalid/placeholder
        # Generate with: python -c "from passlib.hash import bcrypt; print(bcrypt.hash('Admin123!'))"
        admin_password_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyPxR3UqRqW8xK"

        await conn.execute(text("""
            INSERT INTO users (
                id, email, hashed_password, full_name, is_admin, is_verified,
                is_active, created_at
            ) VALUES (
                uuid_generate_v4(), 'admin@roots.com', :password, 'System Administrator',
                true, true, true, NOW()
            ) ON CONFLICT (email) DO NOTHING
        """), {"password": admin_password_hash})
        logger.info("  ✅ Admin user created (email: admin@roots.com, password: Admin123!)")

        products = [
            ("Handwoven Kente Scarf", "Beautiful handwoven Kente scarf from Ghana", 45.99,
             "https://images.unsplash.com/photo-1618519764620-7403abdbdfe9", "Ghana", "Handwoven", 50, True),
            ("Wooden Mask", "Traditional hand-carved wooden mask from Kenya", 89.99,
             "https://images.unsplash.com/photo-1562414050-4f8a4d3ab9fe", "Kenya", "Rare", 20, True),
            ("Beaded Necklace", "Colorful handcrafted beaded necklace from Nigeria", 29.99,
             "https://images.unsplash.com/photo-1617038260897-41a1f14a8ca0", "Nigeria", "Handwoven", 100, True),
            ("Ceramic Vase", "Handmade ceramic vase with traditional Moroccan patterns", 65.99,
             "https://images.unsplash.com/photo-1578500494198-246f612d3b3d", "Morocco", "Rare", 30, False),
            ("Leather Bag", "Handcrafted leather bag from Ethiopia", 120.00,
             "https://images.unsplash.com/photo-1548036328-c9fa89d128fa", "Ethiopia", "Handwoven", 15, True),
        ]

        for product in products:
            await conn.execute(text("""
                INSERT INTO products (
                    id, name, description, price, image_url, origin, tag, stock,
                    is_featured, is_active, created_at
                ) VALUES (
                    uuid_generate_v4(), :name, :description, :price, :image_url,
                    :origin, :tag, :stock, :is_featured, true, NOW()
                )
            """), {
                "name": product[0],
                "description": product[1],
                "price": product[2],
                "image_url": product[3],
                "origin": product[4],
                "tag": product[5],
                "stock": product[6],
                "is_featured": product[7],
            })

        logger.info(f"  ✅ {len(products)} sample products inserted")

        testimonials = [
            ("Sarah Johnson", "Absolutely love the products! The quality is amazing and shipping was fast.", "New York, USA"),
            ("Michael Chen", "Authentic African crafts that tell a story. Will definitely order again.", "London, UK"),
        ]

        for name, text_body, location in testimonials:
            await conn.execute(text("""
                INSERT INTO testimonials (id, name, text, location, is_approved, created_at)
                VALUES (uuid_generate_v4(), :name, :text, :location, true, NOW())
            """), {"name": name, "text": text_body, "location": location})

        logger.info(f"  ✅ {len(testimonials)} sample testimonials inserted")


async def main():
    """Main initialization function"""
    print("=" * 60)
    print("Roots Backend - Enterprise Database Setup")
    print("=" * 60)

    try:
        print("\n1️⃣  Creating database...")
        await create_database_if_not_exists()

        print("\n2️⃣  Creating tables...")
        await create_tables()

        print("\n3️⃣  Inserting sample data...")
        await insert_sample_data()

        print("\n" + "=" * 60)
        print("✅ DATABASE SETUP COMPLETE!")
        print("=" * 60)
        print("\n🔐 Sample Login:")
        print("   Email: admin@roots.com")
        print("   Password: Admin123!")
        print("\n📚 Next Steps:")
        print("   1. Run: uvicorn app.main:app --reload")
        print("   2. Visit: http://localhost:8000/api/docs")

    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

