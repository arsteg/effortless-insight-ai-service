"""
Unit tests for utility modules
"""

import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch

from app.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerConfig,
    CircuitOpenError,
    get_circuit_breaker,
)
from app.utils.retry import retry_async, retry_sync, RetryConfig
from app.utils.token_counter import TokenCounter


class TestCircuitBreakerConfig:
    """Test cases for circuit breaker configuration"""

    def test_default_config(self):
        """Test default configuration"""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 30.0
        assert config.half_open_max_calls == 3

    def test_custom_config(self):
        """Test custom configuration"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=1,
            timeout=10.0,
            half_open_max_calls=5
        )
        assert config.failure_threshold == 3
        assert config.success_threshold == 1
        assert config.timeout == 10.0
        assert config.half_open_max_calls == 5


class TestCircuitBreaker:
    """Test cases for circuit breaker"""

    def test_initial_state_closed(self):
        """Test initial state is closed"""
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_record_success_keeps_closed(self):
        """Test success keeps circuit closed"""
        cb = CircuitBreaker("test")
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_record_failure_increments_count(self):
        """Test failure increments count"""
        cb = CircuitBreaker("test")
        cb.record_failure()
        assert cb._failure_count == 1
        assert cb.state == CircuitState.CLOSED

    def test_threshold_opens_circuit(self):
        """Test reaching threshold opens circuit"""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config=config)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_can_execute_when_closed(self):
        """Test circuit allows execution when closed"""
        cb = CircuitBreaker("test")
        assert cb.can_execute() is True

    def test_cannot_execute_when_open(self):
        """Test circuit blocks execution when open"""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config=config)
        for _ in range(3):
            cb.record_failure()
        assert cb.can_execute() is False

    def test_half_open_after_timeout(self):
        """Test circuit transitions to half-open after timeout"""
        config = CircuitBreakerConfig(failure_threshold=3, timeout=0.1)
        cb = CircuitBreaker("test", config=config)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Check state should transition to half-open
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_in_half_open_closes(self):
        """Test success in half-open state closes circuit"""
        config = CircuitBreakerConfig(failure_threshold=3, timeout=0.1, success_threshold=1)
        cb = CircuitBreaker("test", config=config)
        for _ in range(3):
            cb.record_failure()

        time.sleep(0.15)
        _ = cb.state  # Trigger transition to half-open

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_failure_in_half_open_opens(self):
        """Test failure in half-open state opens circuit"""
        config = CircuitBreakerConfig(failure_threshold=3, timeout=0.1)
        cb = CircuitBreaker("test", config=config)
        for _ in range(3):
            cb.record_failure()

        time.sleep(0.15)
        _ = cb.state  # Trigger transition to half-open

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_reset(self):
        """Test reset clears state"""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config=config)
        for _ in range(3):
            cb.record_failure()
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorator with successful call"""
        cb = CircuitBreaker("test")

        @cb
        async def success_func():
            return "success"

        result = await success_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_failure(self):
        """Test decorator records failure"""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config=config)

        @cb
        async def failing_func():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await failing_func()

        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_decorator_circuit_open(self):
        """Test decorator raises when circuit is open"""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config=config)
        cb.record_failure()  # Open the circuit

        @cb
        async def blocked_func():
            return "success"

        with pytest.raises(CircuitOpenError):
            await blocked_func()

    def test_get_circuit_breaker(self):
        """Test get_circuit_breaker returns cached instance"""
        cb1 = get_circuit_breaker("shared")
        cb2 = get_circuit_breaker("shared")
        assert cb1 is cb2

    def test_get_circuit_breaker_different_names(self):
        """Test different names return different instances"""
        cb1 = get_circuit_breaker("service1")
        cb2 = get_circuit_breaker("service2")
        assert cb1 is not cb2


class TestRetryConfig:
    """Test cases for retry configuration"""

    def test_default_config(self):
        """Test default configuration"""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_config(self):
        """Test custom configuration"""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=False
        )
        assert config.max_attempts == 5
        assert config.initial_delay == 2.0
        assert config.max_delay == 120.0
        assert config.exponential_base == 3.0
        assert config.jitter is False


class TestRetryAsync:
    """Test cases for async retry decorator"""

    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        """Test successful call doesn't retry"""
        call_count = 0

        @retry_async(max_attempts=3)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test retry on failure"""
        call_count = 0

        @retry_async(max_attempts=3, initial_delay=0.01)
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = await failing_then_success()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self):
        """Test exception raised after max attempts"""
        call_count = 0

        @retry_async(max_attempts=2, initial_delay=0.01)
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            await always_fail()

        assert call_count == 2  # 2 attempts total

    @pytest.mark.asyncio
    async def test_retry_specific_exceptions(self):
        """Test retry only on specific exceptions"""
        call_count = 0

        @retry_async(max_attempts=3, initial_delay=0.01, exceptions=(ValueError,))
        async def type_error_func():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retried")

        with pytest.raises(TypeError):
            await type_error_func()

        assert call_count == 1  # No retries for TypeError

    @pytest.mark.asyncio
    async def test_with_config_object(self):
        """Test using RetryConfig object"""
        call_count = 0
        config = RetryConfig(max_attempts=2, initial_delay=0.01)

        @retry_async(config=config)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()
        assert result == "success"


class TestRetrySyncDecorator:
    """Test cases for sync retry decorator"""

    def test_success_no_retry(self):
        """Test successful call doesn't retry"""
        call_count = 0

        @retry_sync(max_attempts=3)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure(self):
        """Test retry on failure"""
        call_count = 0

        @retry_sync(max_attempts=3, initial_delay=0.01)
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = failing_then_success()
        assert result == "success"
        assert call_count == 3


class TestTokenCounter:
    """Test cases for token counter"""

    def test_count_tokens_simple(self):
        """Test counting tokens in simple text"""
        counter = TokenCounter()
        text = "Hello, how are you?"
        count = counter.count_tokens(text)
        assert count > 0
        assert count < 20  # Reasonable for this text

    def test_count_tokens_empty(self):
        """Test counting tokens in empty text"""
        counter = TokenCounter()
        count = counter.count_tokens("")
        assert count == 0

    def test_count_tokens_long_text(self):
        """Test counting tokens in long text"""
        counter = TokenCounter()
        text = "This is a test sentence. " * 100
        count = counter.count_tokens(text)
        assert count > 100

    def test_count_tokens_list(self):
        """Test counting tokens in list of texts"""
        counter = TokenCounter()
        texts = ["Hello world", "This is a test"]
        count = counter.count_tokens_list(texts)
        assert count > 0

    def test_count_chat_tokens(self):
        """Test counting chat message tokens"""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        count = counter.count_chat_tokens(messages)
        assert count > 0
        # Should include overhead
        assert count > counter.count_tokens("Hello") + counter.count_tokens("Hi there!")

    def test_estimate_cost_gpt4(self):
        """Test cost estimation for GPT-4"""
        counter = TokenCounter()
        input_tokens = 1000
        output_tokens = 500
        cost = counter.estimate_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model="gpt-4-turbo"
        )
        assert cost > 0

    def test_estimate_cost_gpt35(self):
        """Test cost estimation for GPT-3.5"""
        counter = TokenCounter()
        input_tokens = 1000
        output_tokens = 500
        cost = counter.estimate_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model="gpt-3.5-turbo"
        )
        assert cost > 0

    def test_estimate_cost_gpt4_more_expensive(self):
        """Test GPT-4 is more expensive than GPT-3.5"""
        counter = TokenCounter()
        gpt4_cost = counter.estimate_cost(1000, 500, "gpt-4-turbo")
        gpt35_cost = counter.estimate_cost(1000, 500, "gpt-3.5-turbo")
        assert gpt4_cost > gpt35_cost

    def test_truncate_to_tokens(self):
        """Test truncating text to token limit"""
        counter = TokenCounter()
        text = "This is a test. " * 1000
        truncated = counter.truncate_to_tokens(text, max_tokens=100)

        truncated_count = counter.count_tokens(truncated)
        assert truncated_count <= 100

    def test_truncate_short_text_unchanged(self):
        """Test short text is not truncated"""
        counter = TokenCounter()
        text = "Short text"
        truncated = counter.truncate_to_tokens(text, max_tokens=1000)
        assert truncated == text

    def test_split_into_chunks(self):
        """Test splitting text into token-limited chunks"""
        counter = TokenCounter()
        text = "Sentence one. Sentence two. Sentence three. " * 100
        # Use max_tokens > overlap_tokens (default 100) to avoid infinite loop
        chunks = counter.split_into_chunks(text, max_tokens=150, overlap_tokens=20)

        assert len(chunks) > 1
        for chunk in chunks:
            assert counter.count_tokens(chunk) <= 155  # Allow small variance

    def test_split_short_text_single_chunk(self):
        """Test short text returns single chunk"""
        counter = TokenCounter()
        text = "Short text"
        chunks = counter.split_into_chunks(text, max_tokens=100)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_different_models(self):
        """Test counter works with different models"""
        counter_gpt4 = TokenCounter("gpt-4")
        counter_gpt35 = TokenCounter("gpt-3.5-turbo")

        text = "Hello world"
        # Both should return similar counts
        assert counter_gpt4.count_tokens(text) > 0
        assert counter_gpt35.count_tokens(text) > 0
