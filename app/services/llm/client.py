"""
OpenAI client wrapper with retry logic and response caching
"""

import time
import hashlib
import json
from typing import Optional, Dict, Any, List
import structlog
from openai import AsyncOpenAI, APIError, RateLimitError

from app.core.config import settings

logger = structlog.get_logger()


class LLMResponseCache:
    """
    Simple in-memory cache for LLM responses.
    Caches based on prompt hash to avoid redundant API calls.
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self._cache: Dict[str, tuple[Dict[str, Any], float]] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0

    def _generate_key(self, messages: List[Dict[str, str]], model: str, temperature: float) -> str:
        """Generate a unique cache key from the request parameters"""
        content = json.dumps({
            "messages": messages,
            "model": model,
            "temperature": temperature
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, messages: List[Dict[str, str]], model: str, temperature: float) -> Optional[Dict[str, Any]]:
        """Get a cached response if available and not expired"""
        key = self._generate_key(messages, model, temperature)

        if key in self._cache:
            response, cached_at = self._cache[key]
            if time.time() - cached_at < self._ttl_seconds:
                self._hits += 1
                logger.debug("LLM cache hit", key=key[:16])
                return response

            # Expired, remove it
            del self._cache[key]

        self._misses += 1
        return None

    def set(self, messages: List[Dict[str, str]], model: str, temperature: float, response: Dict[str, Any]):
        """Cache a response"""
        # Evict oldest entries if cache is full
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        key = self._generate_key(messages, model, temperature)
        self._cache[key] = (response, time.time())
        logger.debug("LLM response cached", key=key[:16])

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
            "ttl_seconds": self._ttl_seconds
        }

    def clear(self):
        """Clear the cache"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0


# Global cache instance
_llm_cache = LLMResponseCache()


class LLMClient:
    """
    OpenAI client wrapper with retry logic and token tracking

    Features:
    - Automatic retry on rate limits
    - Token counting
    - Cost estimation
    """

    # Pricing per 1M tokens (as of 2024)
    PRICING = {
        "gpt-4-turbo-preview": {"input": 10.0, "output": 30.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    }

    def __init__(self, model: Optional[str] = None, enable_cache: bool = True):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.openai_model
        self.default_temperature = 0.2
        self.enable_cache = enable_cache

        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
        json_mode: bool = False,
        retry_count: int = 3,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Send completion request with retry logic and optional caching

        Args:
            messages: Chat messages
            temperature: Temperature setting
            max_tokens: Maximum output tokens
            json_mode: Enable JSON mode
            retry_count: Number of retries
            use_cache: Whether to use caching for this request

        Returns:
            Dict with response content and usage stats
        """
        temperature = temperature if temperature is not None else self.default_temperature

        # Check cache for identical requests (only for deterministic settings)
        if self.enable_cache and use_cache and temperature <= 0.3:
            cached = _llm_cache.get(messages, self.model, temperature)
            if cached:
                # Return cached response with cache indicator
                return {**cached, "cached": True}

        for attempt in range(retry_count):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }

                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                start_time = time.time()
                response = await self.client.chat.completions.create(**kwargs)
                elapsed = time.time() - start_time

                # Track tokens
                usage = response.usage
                self.total_input_tokens += usage.prompt_tokens
                self.total_output_tokens += usage.completion_tokens

                result = {
                    "content": response.choices[0].message.content,
                    "input_tokens": usage.prompt_tokens,
                    "output_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "model": self.model,
                    "finish_reason": response.choices[0].finish_reason,
                    "cached": False,
                }

                logger.debug(
                    "LLM completion",
                    model=self.model,
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    elapsed_s=round(elapsed, 2)
                )

                # Cache the response for deterministic settings
                if self.enable_cache and use_cache and temperature <= 0.3:
                    _llm_cache.set(messages, self.model, temperature, result)

                return result

            except RateLimitError as e:
                if attempt < retry_count - 1:
                    wait_time = (2 ** attempt) * 2  # Exponential backoff
                    logger.warning(
                        "Rate limited, retrying",
                        attempt=attempt + 1,
                        wait_time=wait_time
                    )
                    await self._async_sleep(wait_time)
                else:
                    raise

            except APIError as e:
                logger.error("OpenAI API error", error=str(e))
                raise

    async def _async_sleep(self, seconds: float):
        """Async sleep for retry backoff"""
        import asyncio
        await asyncio.sleep(seconds)

    def estimate_cost(self) -> float:
        """
        Estimate cost based on token usage

        Returns:
            Estimated cost in USD
        """
        pricing = self.PRICING.get(self.model, {"input": 10.0, "output": 30.0})

        input_cost = (self.total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.total_output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "model": self.model,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": self.estimate_cost(),
        }

    def reset_usage(self):
        """Reset usage counters"""
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def is_available(self) -> bool:
        """Check if OpenAI API is available"""
        try:
            await self.client.models.retrieve(self.model)
            return True
        except Exception:
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get LLM response cache statistics"""
        return _llm_cache.get_stats()

    def clear_cache(self):
        """Clear the LLM response cache"""
        _llm_cache.clear()
        logger.info("LLM response cache cleared")
