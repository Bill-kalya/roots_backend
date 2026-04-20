import subprocess
import sys
import logging

logger = logging.getLogger(__name__)


def run_migrations():
    try:
        logger.info("🚀 Running database migrations...")

        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True
        )

        logger.info(result.stdout)
        logger.info("✅ Migrations completed successfully")

    except subprocess.CalledProcessError as e:
        logger.error("❌ Migration failed")
        logger.error(e.stdout)
        logger.error(e.stderr)
        sys.exit(1)
