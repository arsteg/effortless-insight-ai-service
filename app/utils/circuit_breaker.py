"""
Circuit breaker pattern implementation
"""

import asyncio
import time
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failures exceeded threshold
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 30.0  # Seconds before trying again
    half_open_max_calls: int = 3


class CircuitBreaker:
    """
    Circuit breaker for handling cascading failures

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail fast
    - HALF_OPEN: Testing recovery, limited requests allowed

    Usage:
        breaker = CircuitBreaker("external-api")

        @breaker
        async def call_external_api():
            ...

        # Or manual usage
        if breaker.can_execute():
            try:
                result = await call_api()
                breaker.record_success()
            except Exception:
                breaker.record_failure()
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        self._check_timeout()
        return self._state

    def can_execute(self) -> bool:
        """Check if execution is allowed"""
        self._check_timeout()

        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.config.half_open_max_calls

        return False

    def record_success(self):
        """Record a successful execution"""
        self._failure_count = 0

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self._state == CircuitState.CLOSED:
            self._success_count += 1

    def record_failure(self):
        """Record a failed execution"""
        self._failure_count += 1
        self._success_count = 0
        self._last_failure_time = time.time()

        if self._failure_count >= self.config.failure_threshold:
            self._transition_to_open()

    def _check_timeout(self):
        """Check if timeout has elapsed and transition to half-open"""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.config.timeout:
                self._transition_to_half_open()

    def _transition_to_open(self):
        """Transition to open state"""
        if self._state != CircuitState.OPEN:
            logger.warning(
                "Circuit breaker opened",
                name=self.name,
                failures=self._failure_count
            )
        self._state = CircuitState.OPEN

    def _transition_to_half_open(self):
        """Transition to half-open state"""
        logger.info("Circuit breaker half-open", name=self.name)
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        self._success_count = 0

    def _transition_to_closed(self):
        """Transition to closed state"""
        logger.info("Circuit breaker closed", name=self.name)
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

    def __call__(self, func: Callable):
        """Decorator usage"""
        import functools

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not self.can_execute():
                raise CircuitOpenError(f"Circuit {self.name} is open")

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1

            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result

            except Exception as e:
                self.record_failure()
                raise

        return wrapper

    def reset(self):
        """Manually reset the circuit breaker"""
        self._transition_to_closed()


class CircuitOpenError(Exception):
    """Exception raised when circuit is open"""
    pass


# Global circuit breakers for external services
_circuit_breakers: dict = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker by name"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name)
    return _circuit_breakers[name]
