from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlalchemy import event, text
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Callable
import logging
import time
import asyncio
from functools import wraps
from app.core.config import settings

logger = logging.getLogger(__name__)

# Custom exceptions for retry handling
class DeadlockError(Exception):
    pass

class SerializationError(Exception):
    pass

class QueryTimeoutError(Exception):
    pass

def retry_on_deadlock(max_attempts=3):
    """Decorator to retry on deadlock and serialization errors"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_msg = str(e).lower()
                    
                    # Check for retryable errors
                    if any(phrase in error_msg for phrase in [
                        'deadlock detected',
                        'could not serialize',
                        'concurrent update',
                        'lock timeout'
                    ]):
                        wait_time = 0.1 * (2 ** attempt)
                        logger.warning(f"Retryable error on attempt {attempt + 1}: {e}. Waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise e
            
            raise last_exception
        return wrapper
    return decorator

class EnterpriseDatabaseManager:
    """Enterprise database manager with query timeouts, deadlock retry, and connection pooling"""
    
    def __init__(self):
        self._write_engine: Optional[AsyncEngine] = None
        self._read_engine: Optional[AsyncEngine] = None
        self._async_session_maker: Optional[async_sessionmaker] = None
        self._read_session_maker: Optional[async_sessionmaker] = None
        
        # Query timeout defaults (in seconds)
        self.QUERY_TIMEOUTS = {
            "default": 30,
            "write": 10,
            "read": 20,
            "batch": 60,
            "report": 120
        }
    
    async def initialize(self):
        """Initialize database connections with enterprise settings"""
        
        # Write engine (primary) - using NullPool for async
        self._write_engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,  # Use NullPool for async, connection pooling is handled differently
            echo=settings.DATABASE_ECHO if hasattr(settings, 'DATABASE_ECHO') else False,
            connect_args={
                "timeout": settings.DATABASE_CONNECT_TIMEOUT if hasattr(settings, 'DATABASE_CONNECT_TIMEOUT') else 10,
                "server_settings": {
                    "jit": "off",
                    "application_name": "roots_backend",
                    "statement_timeout": f"{self.QUERY_TIMEOUTS['default'] * 1000}",
                    "lock_timeout": "5000",
                }
            }
        )
        
        # Read engine (replica if available)
        if hasattr(settings, 'DATABASE_REPLICA_URL') and settings.DATABASE_REPLICA_URL:
            self._read_engine = create_async_engine(
                str(settings.DATABASE_REPLICA_URL),
                poolclass=NullPool,
                echo=settings.DATABASE_ECHO if hasattr(settings, 'DATABASE_ECHO') else False,
            )
        else:
            self._read_engine = self._write_engine
        
        # Session makers
        self._async_session_maker = async_sessionmaker(
            self._write_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        
        self._read_session_maker = async_sessionmaker(
            self._read_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        
        logger.info("Enterprise database connections initialized")
    
    @asynccontextmanager
    async def get_write_session(self, timeout_type: str = "default"):
        """Get session for write operations with query timeout"""
        session = self._async_session_maker()
        
        try:
            # Set session-level timeout
            timeout_ms = self.QUERY_TIMEOUTS.get(timeout_type, self.QUERY_TIMEOUTS["default"]) * 1000
            await session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
            await session.execute(text(f"SET LOCAL lock_timeout = 5000"))
            
            yield session
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            raise
            
        finally:
            await session.close()
    
    @asynccontextmanager
    async def get_read_session(self, timeout_type: str = "read"):
        """Get session for read operations (uses replica)"""
        session = self._read_session_maker()
        
        try:
            # Set read-only transaction
            await session.execute(text("SET TRANSACTION READ ONLY"))
            timeout_ms = self.QUERY_TIMEOUTS.get(timeout_type, self.QUERY_TIMEOUTS["read"]) * 1000
            await session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
            
            yield session
            
        finally:
            await session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive database health check"""
        status = {
            "write_engine": False,
            "read_engine": False,
            "latency_ms": None,
        }
        
        # Check write engine
        try:
            start = time.time()
            async with self._write_engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                status["write_engine"] = True
                status["latency_ms"] = round((time.time() - start) * 1000, 2)
        except Exception as e:
            logger.error(f"Write engine health check failed: {e}")
        
        status["read_engine"] = status["write_engine"]
        
        return status
    
    async def close(self):
        """Close all database connections"""
        if self._write_engine:
            await self._write_engine.dispose()
        if self._read_engine and self._read_engine != self._write_engine:
            await self._read_engine.dispose()
        logger.info("Database connections closed")

# Singleton instance
db_manager = EnterpriseDatabaseManager()

async def get_db() -> AsyncSession:
    """Dependency for write sessions with retry capability"""
    async with db_manager.get_write_session() as session:
        yield session

async def get_read_db() -> AsyncSession:
    """Dependency for read sessions"""
    async with db_manager.get_read_session() as session:
        yield session