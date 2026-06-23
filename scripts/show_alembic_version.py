import sys
from pathlib import Path
# Ensure project root is on sys.path so `app` package imports work
proj_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(proj_root))

from app.core.config import settings
from sqlalchemy import create_engine, text

url = settings.DATABASE_URL
if url.startswith('postgresql://'):
    url = url.replace('postgresql://','postgresql+psycopg2://',1)
engine = create_engine(url)
with engine.connect() as conn:
    r = conn.execute(text('SELECT version_num FROM alembic_version'))
    rows = r.fetchall()
    print(rows)
