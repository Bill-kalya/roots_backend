from typing import Any, Callable, Optional, Dict
from enum import Enum
import hashlib
import json
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.cache.redis_manager import redis_manager
from app.db.session import db_manager
import asyncio

class CacheStrategy(Enum):
    """Cache strategy patterns"""
    CACHE_ASIDE = "cache_aside"
    READ_THROUGH = "read_through"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    REFRESH_AHEAD = "refresh_ahead"

class InvalidationStrategy(Enum):
    """Cache invalidation strategies"""
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    WRITE_INVALIDATE = "write_invalidate"
    WRITE_UPDATE = "write_update"

class CacheManager:
    """Enterprise cache management with strategies"""
    
    def __init__(self):
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "writes": 0,
            "invalidations": 0
        }
    
    async def get_or_set(
        self,
        key: str,
        fetcher: Callable,
        ttl: int = 300,
        strategy: CacheStrategy = CacheStrategy.CACHE_ASIDE
    ) -> Any:
        """Get from cache or fetch and store"""
        
        if strategy == CacheStrategy.CACHE_ASIDE:
            return await self._cache_aside(key, fetcher, ttl)
        elif strategy == CacheStrategy.READ_THROUGH:
            return await self._read_through(key, fetcher, ttl)
        else:
            return await self._cache_aside(key, fetcher, ttl)
    
    async def _cache_aside(self, key: str, fetcher: Callable, ttl: int) -> Any:
        """Cache-aside pattern (lazy loading)"""
        # Try to get from cache
        cached = await redis_manager.get(key)
        
        if cached:
            self.cache_stats["hits"] += 1
            return json.loads(cached)
        
        # Cache miss - fetch data
        self.cache_stats["misses"] += 1
        data = await fetcher()
        
        # Store in cache
        if data:
            await redis_manager.set(key, json.dumps(data, default=str), ttl)
            self.cache_stats["writes"] += 1
        
        return data
    
    async def _read_through(self, key: str, fetcher: Callable, ttl: int) -> Any:
        """Read-through cache pattern"""
        # Always read through cache
        return await self._cache_aside(key, fetcher, ttl)
    
    async def write_through(
        self,
        key: str,
        data: Any,
        writer: Callable,
        ttl: int = 300
    ) -> Any:
        """Write-through cache pattern"""
        # Write to database first
        result = await writer(data)
        
        # Update cache
        await redis_manager.set(key, json.dumps(result, default=str), ttl)
        self.cache_stats["writes"] += 1
        
        return result
    
    async def write_behind(
        self,
        key: str,
        data: Any,
        writer: Callable,
        ttl: int = 300
    ) -> Any:
        """Write-behind cache pattern (async write)"""
        # Update cache immediately
        await redis_manager.set(key, json.dumps(data, default=str), ttl)
        self.cache_stats["writes"] += 1
        
        # Queue database write
        asyncio.create_task(self._async_write(writer, data))
        
        return data
    
    async def _async_write(self, writer: Callable, data: Any):
        """Background database write"""
        try:
            await writer(data)
        except Exception as e:
            # Log failure - would need retry queue in production
            print(f"Write-behind failed: {e}")
    
    async def invalidate(
        self,
        key: str,
        strategy: InvalidationStrategy = InvalidationStrategy.WRITE_INVALIDATE,
        pattern: str = None
    ):
        """Invalidate cache entries"""
        
        if strategy == InvalidationStrategy.TIME_BASED:
            # Just let TTL expire
            pass
            
        elif strategy == InvalidationStrategy.EVENT_BASED:
            # Invalidate on specific events
            await redis_manager.delete(key)
            self.cache_stats["invalidations"] += 1
            
        elif strategy == InvalidationStrategy.WRITE_INVALIDATE:
            # Invalidate when data changes
            await redis_manager.delete(key)
            self.cache_stats["invalidations"] += 1
            
        elif pattern:
            # Invalidate by pattern
            keys = await redis_manager._client.keys(pattern)
            if keys:
                await redis_manager.delete(*keys)
                self.cache_stats["invalidations"] += len(keys)
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        hit_rate = self.cache_stats["hits"] / max(1, self.cache_stats["hits"] + self.cache_stats["misses"])
        
        return {
            **self.cache_stats,
            "hit_rate": round(hit_rate * 100, 2),
            "efficiency": "good" if hit_rate > 0.7 else "poor"
        }

async def get_cache_db_session() -> AsyncSession:
    """Get db session for cache warming"""
    async with db_manager.get_write_session() as session:
        yield session


class CacheWarmer:
    """Pre-warm cache for better performance"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.warmup_tasks = []
    
    async def warmup_products(self):
        """Pre-cache popular products"""
        from app.services.product_service import ProductService
        
        # Cache featured products
        async def fetch_featured():
            async for db in get_cache_db_session():
                service = ProductService(db)
                return await service.get_featured_products(limit=6)
        
        await self.cache_manager.get_or_set(
            "products:featured",
            fetch_featured,
            ttl=600
        )
        
        # Cache top categories
        categories = ["Rare", "Handwoven", "Bestsellers"]
        for category in categories:
            async def fetch_category(cat=category):
                from app.services.product_service import ProductService
                async for db in get_cache_db_session():
                    service = ProductService(db)
                    return await service.get_products_by_tag(cat)
            await self.cache_manager.get_or_set(
                f"products:category:{category}",
                fetch_category,
                ttl=300
            )
    
    async def warmup_user_data(self, user_id: str):
        """Pre-cache user-specific data"""
        # Cache user cart
        await self.cache_manager.get_or_set(
            f"cart:{user_id}",
            lambda: self._get_user_cart(user_id),
            ttl=1800
        )
    
    async def start_warmup(self):
        """Start cache warming in background"""
        tasks = [
            self.warmup_products(),
        ]
        await asyncio.gather(*tasks)

# Cache versioning for zero-downtime updates
class CacheVersioning:
    """Handle cache versioning for schema changes"""
    
    def __init__(self):
        self.current_version = 2  # Increment when data structure changes
    
    def version_key(self, base_key: str) -> str:
        """Add version to cache key"""
        return f"v{self.current_version}:{base_key}"
    
    async def migrate(self, old_version: int):
        """Migrate cache from old version"""
        # Invalidate all old version keys
        pattern = f"v{old_version}:*"
        keys = await redis_manager._client.keys(pattern)
        if keys:
            await redis_manager.delete(*keys)

# Global cache manager
cache_manager = CacheManager()
cache_warmer = CacheWarmer(cache_manager)
cache_versioning = CacheVersioning()