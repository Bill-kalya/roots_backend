import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    url = settings.DATABASE_URL
    if url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT version_num FROM alembic_version'))
        rows = result.fetchall()
        print(rows)

asyncio.run(main())
