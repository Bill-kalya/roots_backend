import subprocess
import logging
import os
import sys


logger = logging.getLogger(__name__)


def run_migrations():
    try:
        logger.info("🚀 Running database migrations...")

        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True
        )

        # alembic upgrade --head output can be very verbose
        if result.stdout:
            logger.info(result.stdout)

        logger.info("✅ Migrations completed successfully")

    except subprocess.CalledProcessError as e:
        logger.error("❌ Migration failed")
        logger.error(e.stdout)
        logger.error(e.stderr)

        # Non-fatal: migrations should not take down the entire API process.
        # In development you may want to stop the server, but default behavior is fail-soft.
        if os.getenv("FAIL_ON_MIGRATION_ERROR", "false").lower() in {"1", "true", "yes", "y"}:
            raise RuntimeError(f"Alembic migration failed: {e.stderr}") from e

        logger.warning("Continuing startup despite migration failure (set FAIL_ON_MIGRATION_ERROR=true to fail hard)")
        return

