import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

OLD_REV = 'merge_a1c2b3d4e5f6_add_testimonials'
NEW_REV = 'merge_a1c2b3d4e5f6'

async def main():
    url = settings.DATABASE_URL
    if url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        result = await conn.execute(text('SELECT version_num FROM alembic_version'))
        rows = result.fetchall()
        print('before:', rows)
        if len(rows) != 1:
            raise SystemExit('Unexpected alembic_version row count: ' + str(len(rows)))
        if rows[0][0] != OLD_REV:
            raise SystemExit(f"Unexpected current revision: {rows[0][0]}\nExpected {OLD_REV}")
        await conn.execute(text('UPDATE alembic_version SET version_num = :new_rev WHERE version_num = :old_rev'), {'new_rev': NEW_REV, 'old_rev': OLD_REV})
        result = await conn.execute(text('SELECT version_num FROM alembic_version'))
        print('after:', result.fetchall())

asyncio.run(main())
