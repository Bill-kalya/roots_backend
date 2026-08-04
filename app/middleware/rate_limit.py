from fastapi import Request, status
from fastapi.responses import JSONResponse
from typing import Dict, Tuple
import time
import logging
from redis import asyncio as aioredis
from app.core.config import settings
logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Resolve the real client IP, honoring X-Forwarded-For behind the proxy.

    Falls back to the socket peer address when the header is absent (local dev).
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # X-Forwarded-For: <client>, <proxy1>, <proxy2>
        first = xff.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


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


# Rate limit by endpoint (exact path). Auth/payment endpoints get strict
# limits because they are the primary brute-force / abuse targets.
RATE_LIMIT_CONFIGS = {
    # Auth — strict brute-force protection
    "/api/auth/login": {"requests": 5, "period": 300},            # 5 per 5 min
    "/api/auth/login/verify-mfa": {"requests": 5, "period": 300}, # 5 per 5 min
    "/api/auth/register": {"requests": 3, "period": 3600},        # 3 per hour
    "/api/auth/forgot-password": {"requests": 5, "period": 3600}, # 5 per hour
    "/api/auth/reset-password": {"requests": 5, "period": 3600},  # 5 per hour
    "/api/auth/resend-verification": {"requests": 5, "period": 300},
    "/api/auth/refresh": {"requests": 60, "period": 300},
    "/api/auth/validate-password": {"requests": 30, "period": 60},
    # Payments — prevent SMS/card-charge abuse
    "/api/payments/mpesa/stk-push": {"requests": 5, "period": 60},
    "/api/payments/paypal/create-order": {"requests": 20, "period": 60},
    "/api/payments/paypal/capture": {"requests": 20, "period": 60},
    "/api/payments/paypal/cancel": {"requests": 20, "period": 60},
    "/api/payments/stripe/create-payment-intent": {"requests": 20, "period": 60},
    "/api/checkout": {"requests": 20, "period": 60},
    "default": {"requests": 100, "period": 60}
}

# Prefix limits apply to all sub-paths (e.g. /api/cart/items, /api/orders/{id}).
# Longest prefix wins over default.
RATE_LIMIT_PREFIXES = {
    "/api/cart": {"requests": 200, "period": 60},
    "/api/orders": {"requests": 50, "period": 60},
    "/api/products": {"requests": 500, "period": 60},
    "/api/user/": {"requests": 200, "period": 60},
    "/api/merchant/": {"requests": 200, "period": 60},
    "/api/admin/": {"requests": 300, "period": 60},
    "/api/payments/mpesa": {"requests": 30, "period": 60},
    "/api/payments/paypal": {"requests": 30, "period": 60},
    "/api/payments/stripe": {"requests": 30, "period": 60},
    "/api/conversations": {"requests": 200, "period": 60},
    "/api/shipping": {"requests": 60, "period": 60},
}

# Never rate-limit signed webhooks, health probes, metrics, static assets,
# or debug helpers (they are auth'd by signature / not user-facing).
RATE_LIMIT_EXEMPT_PREFIXES = (
    "/api/payments/mpesa/callback",
    "/webhooks/paypal",
    "/api/payments/stripe/webhook",
    "/health",
    "/metrics",
    "/uploads",
    "/debug/",
)


def _get_rate_limit_config(path: str) -> Dict:
    if path in RATE_LIMIT_CONFIGS:
        return RATE_LIMIT_CONFIGS[path]
    for prefix, config in sorted(
        RATE_LIMIT_PREFIXES.items(), key=lambda kv: len(kv[0]), reverse=True
    ):
        if path.startswith(prefix):
            return config
    return RATE_LIMIT_CONFIGS["default"]


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""

    path = request.url.path

    # Skip signed webhooks / infra paths entirely.
    if path.startswith(RATE_LIMIT_EXEMPT_PREFIXES):
        return await call_next(request)

    # Get client IP (honors X-Forwarded-For behind the proxy)
    client_ip = get_client_ip(request)
    key = client_ip

    config = _get_rate_limit_config(path)

    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        logger.warning("Redis unavailable, skipping rate limiting")
        return await call_next(request)

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
    for header_name, value in headers.items():
        response.headers[header_name] = str(value)

    return response
