from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time
from typing import Callable
from functools import wraps

# Business metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
)

active_connections = Gauge(
    'active_connections',
    'Active database connections'
)

cart_size = Histogram(
    'cart_size_items',
    'Number of items in cart',
    buckets=(1, 2, 3, 5, 10, 20, 50)
)

order_value = Histogram(
    'order_value_usd',
    'Order total value',
    buckets=(10, 25, 50, 100, 250, 500, 1000, 5000)
)

cache_hit_ratio = Gauge(
    'cache_hit_ratio',
    'Redis cache hit ratio'
)

business_events = Counter(
    'business_events_total',
    'Business events counter',
    ['event_type']
)

# Database metrics
db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['query_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1)
)

db_pool_size = Gauge(
    'db_pool_size',
    'Database connection pool size',
    ['pool_type']
)

# Redis metrics
redis_operation_duration = Histogram(
    'redis_operation_duration_seconds',
    'Redis operation duration',
    ['operation']
)

def track_time(endpoint: str):
    """Decorator to track request duration"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                http_request_duration.labels(
                    method=kwargs.get('request', {}).method if 'request' in kwargs else 'GET',
                    endpoint=endpoint
                ).observe(time.time() - start_time)
                return result
            except Exception as e:
                http_request_duration.labels(
                    method=kwargs.get('request', {}).method if 'request' in kwargs else 'GET',
                    endpoint=endpoint
                ).observe(time.time() - start_time)
                raise
        return wrapper
    return decorator

async def get_metrics():
    """Get Prometheus metrics"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)