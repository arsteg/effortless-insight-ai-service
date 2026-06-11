"""
OpenAI client wrapper with retry logic
"""

import time
from typing import Optional, Dict, Any, List
import structlog
from openai import AsyncOpenAI, APIError, RateLimitError

from app.core.config import settings

logger = structlog.get_logger()


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

    def __init__(self, model: Optional[str] = None):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.openai_model
        self.default_temperature = 0.2

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
    ) -> Dict[str, Any]:
        """
        Send completion request with retry logic

        Args:
            messages: Chat messages
            temperature: Temperature setting
            max_tokens: Maximum output tokens
            json_mode: Enable JSON mode
            retry_count: Number of retries

        Returns:
            Dict with response content and usage stats
        """
        temperature = temperature if temperature is not None else self.default_temperature

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

                logger.debug(
                    "LLM completion",
                    model=self.model,
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    elapsed_s=round(elapsed, 2)
                )

                return {
                    "content": response.choices[0].message.content,
                    "input_tokens": usage.prompt_tokens,
                    "output_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "model": self.model,
                    "finish_reason": response.choices[0].finish_reason,
                }

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
