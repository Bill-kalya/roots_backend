from enum import Enum
from typing import Dict, Any
import time
import asyncio
from functools import wraps

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, don't execute
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    """Circuit breaker for external service calls"""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        
    def record_success(self):
        """Record successful call"""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self._reset()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
            
    def record_failure(self):
        """Record failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.half_open_calls = 0
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            
    def can_execute(self) -> bool:
        """Check if call can be executed"""
        if self.state == CircuitState.CLOSED:
            return True
            
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
            
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
            
        return False
    
    def _reset(self):
        """Reset circuit breaker"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0

# Circuit breakers for external services
circuit_breakers: Dict[str, CircuitBreaker] = {
    "database": CircuitBreaker("database", failure_threshold=3, recovery_timeout=30),
    "redis": CircuitBreaker("redis", failure_threshold=5, recovery_timeout=60),
    "email": CircuitBreaker("email", failure_threshold=10, recovery_timeout=120),
    "payment": CircuitBreaker("payment", failure_threshold=2, recovery_timeout=300),
}

def with_circuit_breaker(service_name: str):
    """Decorator for circuit breaker protection"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cb = circuit_breakers.get(service_name)
            if not cb:
                return await func(*args, **kwargs)
            
            if not cb.can_execute():
                raise Exception(f"Circuit breaker {service_name} is OPEN")
            
            try:
                result = await func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure()
                raise
        return wrapper
    return decorator