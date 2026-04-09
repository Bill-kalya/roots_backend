import asyncio
import logging
from functools import wraps
from typing import Type, Callable, Any, Tuple, Optional, List
from enum import Enum
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
    RetryError
)
from app.core.metrics import db_query_duration

logger = logging.getLogger(__name__)

class RetryStrategy(Enum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    RANDOM_EXPONENTIAL = "random_exponential"
    CONSTANT = "constant"

class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        retryable_exceptions: Optional[List[Type[Exception]]] = None,
        on_retry_callback: Optional[Callable] = None,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.strategy = strategy
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.retryable_exceptions = retryable_exceptions or [
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError
        ]
        self.on_retry_callback = on_retry_callback
        self.jitter = jitter

class RetryManager:
    """Enterprise retry manager with circuit breaker integration"""
    
    def __init__(self):
        self._retry_stats = {}
        
    def get_retry_decorator(self, config: RetryConfig):
        """Create retry decorator with configuration"""
        
        # Configure wait strategy
        if config.strategy == RetryStrategy.EXPONENTIAL:
            wait = wait_exponential(
                multiplier=config.multiplier,
                min=config.initial_delay,
                max=config.max_delay
            )
        elif config.strategy == RetryStrategy.RANDOM_EXPONENTIAL:
            wait = wait_random_exponential(
                multiplier=config.multiplier,
                min=config.initial_delay,
                max=config.max_delay
            )
        elif config.strategy == RetryStrategy.CONSTANT:
            from tenacity import wait_fixed
            wait = wait_fixed(config.initial_delay)
        else:
            from tenacity import wait_none
            wait = wait_none()
        
        # Create retry decorator
        retry_decorator = retry(
            stop=stop_after_attempt(config.max_attempts),
            wait=wait,
            retry=retry_if_exception_type(tuple(config.retryable_exceptions)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True
        )
        
        return retry_decorator
    
    async def retry_async(
        self,
        func: Callable,
        config: RetryConfig,
        *args,
        **kwargs
    ) -> Any:
        """Execute async function with retry logic"""
        
        retry_decorator = self.get_retry_decorator(config)
        
        @retry_decorator
        async def wrapped_func():
            try:
                result = await func(*args, **kwargs)
                self._record_success(func.__name__)
                return result
            except Exception as e:
                self._record_failure(func.__name__, str(e))
                if config.on_retry_callback:
                    await config.on_retry_callback(func.__name__, e)
                raise
        
        return await wrapped_func()
    
    def _record_success(self, func_name: str):
        """Record successful retry"""
        if func_name not in self._retry_stats:
            self._retry_stats[func_name] = {"success": 0, "failure": 0}
        self._retry_stats[func_name]["success"] += 1
    
    def _record_failure(self, func_name: str, error: str):
        """Record failed retry"""
        if func_name not in self._retry_stats:
            self._retry_stats[func_name] = {"success": 0, "failure": 0}
        self._retry_stats[func_name]["failure"] += 1
    
    def get_stats(self) -> dict:
        """Get retry statistics"""
        return self._retry_stats

# Global retry manager
retry_manager = RetryManager()

# Predefined retry configurations
RETRY_CONFIGS = {
    "database": RetryConfig(
        max_attempts=3,
        strategy=RetryStrategy.EXPONENTIAL,
        initial_delay=0.5,
        max_delay=5,
        retryable_exceptions=[ConnectionError, TimeoutError]
    ),
    "redis": RetryConfig(
        max_attempts=5,
        strategy=RetryStrategy.RANDOM_EXPONENTIAL,
        initial_delay=0.1,
        max_delay=2,
        retryable_exceptions=[ConnectionError]
    ),
    "email": RetryConfig(
        max_attempts=4,
        strategy=RetryStrategy.EXPONENTIAL,
        initial_delay=2,
        max_delay=60,
        retryable_exceptions=[ConnectionError, TimeoutError]
    ),
    "payment": RetryConfig(
        max_attempts=2,
        strategy=RetryStrategy.LINEAR,
        initial_delay=1,
        retryable_exceptions=[TimeoutError]
    ),
    "external_api": RetryConfig(
        max_attempts=3,
        strategy=RetryStrategy.RANDOM_EXPONENTIAL,
        initial_delay=1,
        max_delay=30,
        retryable_exceptions=[ConnectionError, TimeoutError]
    )
}

def with_retry(config_key: str):
    """Decorator for retry logic"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = RETRY_CONFIGS.get(config_key, RETRY_CONFIGS["external_api"])
            return await retry_manager.retry_async(func, config, *args, **kwargs)
        return wrapper
    return decorator