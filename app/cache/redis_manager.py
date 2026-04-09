import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
from typing import Optional, Dict, Any
import json
import logging
import time
from contextlib import asynccontextmanager
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisManager:
    """Enterprise Redis connection manager with cluster support"""
    
    def __init__(self):
        self._client: Optional[aioredis.Redis] = None
        self._cluster_client: Optional[aioredis.RedisCluster] = None
        
    async def initialize(self):
        """Initialize Redis connection"""
        if settings.REDIS_CLUSTER and settings.REDIS_CLUSTER_NODES:
            # Cluster mode for production
            from redis.asyncio.cluster import RedisCluster
            self._cluster_client = RedisCluster(
                startup_nodes=settings.REDIS_CLUSTER_NODES,
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
                retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
                health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL,
            )
            await self._cluster_client.initialize()
            self._client = self._cluster_client
        else:
            # Single node or sentinel mode
            connection_pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
                retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
                health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL,
            )
            self._client = aioredis.Redis(connection_pool=connection_pool)
        
        # Test connection
        await self._client.ping()
        logger.info("Redis connection initialized successfully")
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        try:
            return await self._client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: any, 
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """Set value in cache"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            elif not isinstance(value, str):
                value = str(value)
            
            if ttl:
                return await self._client.set(key, value, ex=ttl, nx=nx, xx=xx)
            else:
                return await self._client.set(key, value, nx=nx, xx=xx)
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    async def delete(self, *keys: str) -> int:
        """Delete keys from cache"""
        try:
            return await self._client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis DELETE error for keys {keys}: {e}")
            return 0
    
    async def exists(self, *keys: str) -> int:
        """Check if keys exist"""
        try:
            return await self._client.exists(*keys)
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return 0
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on key"""
        try:
            return await self._client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Redis EXPIRE error for key {key}: {e}")
            return False
    
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter"""
        try:
            return await self._client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis INCR error for key {key}: {e}")
            return None
    
    async def sadd(self, key: str, *values: str) -> int:
        """Add to set"""
        try:
            return await self._client.sadd(key, *values)
        except Exception as e:
            logger.error(f"Redis SADD error: {e}")
            return 0
    
    async def srem(self, key: str, *values: str) -> int:
        """Remove from set"""
        try:
            return await self._client.srem(key, *values)
        except Exception as e:
            logger.error(f"Redis SREM error: {e}")
            return 0
    
    async def smembers(self, key: str) -> set:
        """Get all set members"""
        try:
            return await self._client.smembers(key)
        except Exception as e:
            logger.error(f"Redis SMEMBERS error: {e}")
            return set()
    
    @asynccontextmanager
    async def pipeline(self):
        """Get Redis pipeline for batch operations"""
        async with self._client.pipeline() as pipe:
            yield pipe
            await pipe.execute()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis health"""
        status = {
            "connected": False,
            "latency_ms": None,
            "info": None
        }
        
        try:
            start = time.time()
            await self._client.ping()
            status["connected"] = True
            status["latency_ms"] = round((time.time() - start) * 1000, 2)
            
            info = await self._client.info("stats")
            status["info"] = {
                "total_connections_received": info.get("total_connections_received"),
                "total_commands_processed": info.get("total_commands_processed"),
                "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec"),
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
        
        return status
    
    async def close(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            logger.info("Redis connection closed")

# Singleton instance
redis_manager = RedisManager()

async def get_redis() -> aioredis.Redis:
    """Dependency for Redis client"""
    return redis_manager._client