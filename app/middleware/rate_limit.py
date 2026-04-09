from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Tuple
import time
from redis import asyncio as aioredis
from app.core.config import settings

class RateLimiter:
    """Token bucket rate limiter with Redis"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
    
    async def is_rate_limited(
        self,
        key: str,
        requests: int = settings.RATE_LIMIT_REQUESTS,
        period: int = settings.RATE_LIMIT_PERIOD,
        burst: int = settings.RATE_LIMIT_BURST
    ) -> Tuple[bool, Dict]:
        """Check if request should be rate limited"""
        
        current_time = time.time()
        window_key = f"rate_limit:{key}:{int(current_time / period)}"
        
        # Get current count
        current = await self.redis.get(window_key)
        current_count = int(current) if current else 0
        
        # Get previous window for burst handling
        prev_window_key = f"rate_limit:{key}:{int(current_time / period) - 1}"
        previous = await self.redis.get(prev_window_key)
        previous_count = int(previous) if previous else 0
        
        # Calculate allowed requests (smooth transition between windows)
        elapsed = current_time % period
        allowed = (requests * (period - elapsed) / period) + (burst * elapsed / period)
        
        headers = {
            "X-RateLimit-Limit": str(requests),
            "X-RateLimit-Remaining": str(max(0, int(allowed) - current_count)),
            "X-RateLimit-Reset": str(int(current_time + (period - elapsed)))
        }
        
        if current_count >= allowed:
            return True, headers
        
        # Increment counter
        await self.redis.incr(window_key)
        await self.redis.expire(window_key, period + 1)
        
        return False, headers

# Rate limit by endpoint
RATE_LIMIT_CONFIGS = {
    "/api/auth/login": {"requests": 5, "period": 300},  # 5 per 5 minutes
    "/api/auth/register": {"requests": 3, "period": 3600},  # 3 per hour
    "/api/cart": {"requests": 200, "period": 60},  # 200 per minute
    "/api/orders": {"requests": 50, "period": 60},  # 50 per minute
    "/api/products": {"requests": 500, "period": 60},  # 500 per minute
    "default": {"requests": 100, "period": 60}
}

async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    
    # Get client identifier (IP + User-Agent)
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")
    key = f"{client_ip}:{user_agent}"
    
    # Get endpoint-specific limits
    path = request.url.path
    config = RATE_LIMIT_CONFIGS.get(path, RATE_LIMIT_CONFIGS["default"])
    
    # Check rate limit
    redis = request.app.state.redis
    limiter = RateLimiter(redis)
    limited, headers = await limiter.is_rate_limited(
        key,
        requests=config["requests"],
        period=config["period"]
    )
    
    if limited:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Limit: {config['requests']} per {config['period']} seconds",
                "retry_after": headers.get("X-RateLimit-Reset", 60)
            },
            headers=headers
        )
    
    # Add rate limit headers to response
    response = await call_next(request)
    for key, value in headers.items():
        response.headers[key] = str(value)
    
    return response