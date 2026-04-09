from typing import Dict, Tuple, Optional, List
from enum import Enum
import time
import hashlib
import json
from datetime import datetime, timedelta
from redis import asyncio as aioredis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class RateLimitAlgorithm(Enum):
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    SLIDING_LOG = "sliding_log"

class RateLimitLevel(Enum):
    GLOBAL = "global"
    IP = "ip"
    USER = "user"
    ENDPOINT = "endpoint"
    CUSTOM = "custom"

class AdvancedRateLimiter:
    """Enterprise-grade rate limiter with multiple algorithms"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.algorithm = RateLimitAlgorithm.SLIDING_WINDOW
        
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
        algorithm: RateLimitAlgorithm = None,
        burst: int = None
    ) -> Tuple[bool, Dict]:
        """Check if request exceeds rate limit"""
        
        algorithm = algorithm or self.algorithm
        
        if algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            return await self._token_bucket(key, limit, window, burst or limit)
        elif algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return await self._sliding_window(key, limit, window)
        elif algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            return await self._fixed_window(key, limit, window)
        elif algorithm == RateLimitAlgorithm.SLIDING_LOG:
            return await self._sliding_log(key, limit, window)
        else:
            return await self._sliding_window(key, limit, window)
    
    async def _token_bucket(
        self,
        key: str,
        capacity: int,
        refill_rate: int,
        burst: int
    ) -> Tuple[bool, Dict]:
        """Token bucket algorithm"""
        
        now = time.time()
        bucket_key = f"rate_limit:token:{key}"
        
        # Get current bucket state
        bucket_data = await self.redis.get(bucket_key)
        
        if bucket_data:
            data = json.loads(bucket_data)
            tokens = data["tokens"]
            last_refill = data["last_refill"]
            
            # Calculate tokens to add
            time_passed = now - last_refill
            tokens_to_add = time_passed * (refill_rate / 60)  # Per minute refill
            tokens = min(capacity, tokens + tokens_to_add)
        else:
            tokens = capacity
            last_refill = now
        
        # Check if enough tokens
        if tokens >= 1:
            tokens -= 1
            await self.redis.setex(
                bucket_key,
                3600,
                json.dumps({"tokens": tokens, "last_refill": now})
            )
            
            headers = {
                "X-RateLimit-Limit": str(capacity),
                "X-RateLimit-Remaining": str(int(tokens)),
                "X-RateLimit-Reset": str(int(now + (capacity - tokens) / (refill_rate / 60)))
            }
            return False, headers
        else:
            reset_time = (capacity - tokens) / (refill_rate / 60)
            headers = {
                "X-RateLimit-Limit": str(capacity),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + reset_time)),
                "Retry-After": str(int(reset_time))
            }
            return True, headers
    
    async def _sliding_window(
        self,
        key: str,
        limit: int,
        window: int
    ) -> Tuple[bool, Dict]:
        """Sliding window algorithm (most accurate)"""
        
        now = time.time()
        window_key = f"rate_limit:sliding:{key}"
        window_start = now - window
        
        # Remove old entries
        await self.redis.zremrangebyscore(window_key, 0, window_start)
        
        # Count current requests
        current_count = await self.redis.zcard(window_key)
        
        if current_count < limit:
            # Add current request
            await self.redis.zadd(window_key, {str(now): now})
            await self.redis.expire(window_key, window)
            
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(limit - current_count - 1),
                "X-RateLimit-Reset": str(int(now + window))
            }
            return False, headers
        else:
            # Get oldest request timestamp
            oldest = await self.redis.zrange(window_key, 0, 0, withscores=True)
            reset_time = (oldest[0][1] + window) - now if oldest else window
            
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + reset_time)),
                "Retry-After": str(int(reset_time))
            }
            return True, headers
    
    async def _fixed_window(
        self,
        key: str,
        limit: int,
        window: int
    ) -> Tuple[bool, Dict]:
        """Fixed window algorithm (simplest)"""
        
        now = time.time()
        window_key = f"rate_limit:fixed:{key}:{int(now / window)}"
        
        current = await self.redis.incr(window_key)
        if current == 1:
            await self.redis.expire(window_key, window)
        
        remaining = max(0, limit - current)
        
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(now + window))
        }
        
        return current > limit, headers
    
    async def _sliding_log(
        self,
        key: str,
        limit: int,
        window: int
    ) -> Tuple[bool, Dict]:
        """Sliding log algorithm (most memory intensive but accurate)"""
        
        now = time.time()
        log_key = f"rate_limit:log:{key}"
        window_start = now - window
        
        # Add current request
        await self.redis.lpush(log_key, now)
        await self.redis.ltrim(log_key, 0, limit - 1)
        await self.redis.expire(log_key, window)
        
        # Count requests in window
        requests = await self.redis.lrange(log_key, 0, -1)
        valid_requests = [float(r) for r in requests if float(r) > window_start]
        
        if len(valid_requests) <= limit:
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(limit - len(valid_requests)),
                "X-RateLimit-Reset": str(int(now + window))
            }
            return False, headers
        else:
            oldest = min(valid_requests)
            reset_time = (oldest + window) - now
            
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + reset_time))
            }
            return True, headers

class RateLimitManager:
    """Centralized rate limit management"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.limiter = AdvancedRateLimiter(redis_client)
        self.redis = redis_client
        
        # Rate limit configurations per endpoint
        self.configs = {
            "/api/auth/login": {
                "limit": 5,
                "window": 300,  # 5 minutes
                "algorithm": RateLimitAlgorithm.SLIDING_WINDOW,
                "level": RateLimitLevel.IP
            },
            "/api/auth/register": {
                "limit": 3,
                "window": 3600,  # 1 hour
                "algorithm": RateLimitAlgorithm.FIXED_WINDOW,
                "level": RateLimitLevel.IP
            },
            "/api/auth/refresh": {
                "limit": 10,
                "window": 60,  # 1 minute
                "algorithm": RateLimitAlgorithm.TOKEN_BUCKET,
                "burst": 20
            },
            "/api/cart": {
                "limit": 200,
                "window": 60,  # 200 per minute
                "algorithm": RateLimitAlgorithm.TOKEN_BUCKET,
                "level": RateLimitLevel.USER
            },
            "/api/orders": {
                "limit": 50,
                "window": 60,
                "algorithm": RateLimitAlgorithm.SLIDING_WINDOW,
                "level": RateLimitLevel.USER
            },
            "/api/products": {
                "limit": 500,
                "window": 60,
                "algorithm": RateLimitAlgorithm.TOKEN_BUCKET,
                "level": RateLimitLevel.GLOBAL
            },
            "/api/newsletter/subscribe": {
                "limit": 2,
                "window": 3600,
                "algorithm": RateLimitAlgorithm.FIXED_WINDOW,
                "level": RateLimitLevel.IP
            }
        }
    
    async def get_key(
        self,
        request,
        level: RateLimitLevel,
        user_id: str = None
    ) -> str:
        """Generate rate limit key based on level"""
        
        if level == RateLimitLevel.GLOBAL:
            return "global"
        elif level == RateLimitLevel.IP:
            return f"ip:{request.client.host}"
        elif level == RateLimitLevel.USER:
            return f"user:{user_id or 'anonymous'}"
        elif level == RateLimitLevel.ENDPOINT:
            return f"endpoint:{request.url.path}"
        else:
            return f"custom:{request.client.host}"
    
    async def is_rate_limited(
        self,
        request,
        endpoint: str,
        user_id: str = None
    ) -> Tuple[bool, Dict]:
        """Check if request is rate limited"""
        
        config = self.configs.get(endpoint, self.configs.get("default", {
            "limit": 100,
            "window": 60,
            "algorithm": RateLimitAlgorithm.SLIDING_WINDOW,
            "level": RateLimitLevel.IP
        }))
        
        key = await self.get_key(request, config.get("level", RateLimitLevel.IP), user_id)
        full_key = f"{endpoint}:{key}"
        
        return await self.limiter.check_rate_limit(
            full_key,
            config["limit"],
            config["window"],
            config.get("algorithm"),
            config.get("burst")
        )
    
    async def get_remaining_limits(self, request, endpoint: str) -> Dict:
        """Get remaining rate limits without consuming"""
        # Similar to is_rate_limited but without incrementing
        pass
    
    async def reset_limits(self, endpoint: str, identifier: str):
        """Reset rate limits for specific identifier"""
        pattern = f"rate_limit:*:{endpoint}:{identifier}"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)