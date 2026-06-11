"""
Retry decorators with exponential backoff
"""

import asyncio
import functools
from typing import Callable, Type, Tuple, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    exceptions: Tuple[Type[Exception], ...] = (Exception,)


def retry_async(
    config: Optional[RetryConfig] = None,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator for async functions with retry logic

    Usage:
        @retry_async(max_attempts=3, initial_delay=1.0)
        async def my_function():
            ...

    Args:
        config: RetryConfig object (takes precedence if provided)
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds
        exceptions: Exception types to catch and retry

    Returns:
        Decorated function
    """
    if config is None:
        config = RetryConfig(
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            exceptions=exceptions,
        )

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = config.initial_delay

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except config.exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        logger.error(
                            "Max retries reached",
                            function=func.__name__,
                            attempts=attempt,
                            error=str(e)
                        )
                        raise

                    # Calculate delay with exponential backoff
                    if config.jitter:
                        import random
                        jitter = random.uniform(0, delay * 0.1)
                        actual_delay = delay + jitter
                    else:
                        actual_delay = delay

                    actual_delay = min(actual_delay, config.max_delay)

                    logger.warning(
                        "Retry after error",
                        function=func.__name__,
                        attempt=attempt,
                        delay=actual_delay,
                        error=str(e)
                    )

                    await asyncio.sleep(actual_delay)
                    delay *= config.exponential_base

            raise last_exception

        return wrapper

    return decorator


def retry_sync(
    config: Optional[RetryConfig] = None,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator for sync functions with retry logic

    Usage:
        @retry_sync(max_attempts=3)
        def my_function():
            ...
    """
    if config is None:
        config = RetryConfig(
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            exceptions=exceptions,
        )

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = config.initial_delay

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except config.exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        raise

                    import time
                    time.sleep(delay)
                    delay *= config.exponential_base

            raise last_exception

        return wrapper

    return decorator
