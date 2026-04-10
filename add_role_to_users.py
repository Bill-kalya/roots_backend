import asyncio
import sys
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.user import User, UserRole
from app.db.session import get_db, db_manager
from app.core.config import settings

async def init_db():
    """Initialize database manager before using sessions"""
    print("🔄 Initializing database connections...")
    await db_manager.initialize()
    print("✅ Database ready!")

async def add_roles():
    """Add default USER role to users missing roles"""
    updated_count = 0
    
    async for session in get_db():
        try:
            # Find users without role (NULL or None)
            stmt = select(User).where(User.role.is_(None)).options(selectinload(User))
            result = await session.execute(stmt)
            users = result.scalars().all()
            
            for user in users:
                if user.role is None:
                    user.role = UserRole.USER
                    updated_count += 1
            
            await session.commit()
            print(f"✅ Successfully updated {updated_count} users with default USER role")
            print("Roles added successfully!")
            return
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error: {e}")
            raise

async def dry_run():
    """Dry run - show how many users would be updated"""
    count = 0
    async for session in get_db():
        stmt = select(User).where(User.role.is_(None))
        result = await session.execute(stmt)
        count = result.scalar_one_or_none()
        print(f"ℹ️  Dry run: {count or 0} users need role update")

async def main():
    """Main entrypoint with DB initialization"""
    await init_db()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        await dry_run()
    else:
        print("🚀 Adding roles to users (run with --dry-run first to preview)")
        await add_roles()

if __name__ == "__main__":
    asyncio.run(main())

