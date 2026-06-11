"""
Token counter for LLM operations
"""

from typing import Optional, List
import structlog

logger = structlog.get_logger()

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not available, using approximate token counting")


class TokenCounter:
    """
    Token counter for estimating LLM token usage

    Uses tiktoken for accurate counting, with fallback to approximation.
    """

    # Approximate characters per token for different models
    CHARS_PER_TOKEN = {
        "gpt-4": 4.0,
        "gpt-4-turbo": 4.0,
        "gpt-4o": 4.0,
        "gpt-3.5-turbo": 4.0,
        "text-embedding-3-large": 4.0,
        "default": 4.0,
    }

    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self._encoding = None

        if TIKTOKEN_AVAILABLE:
            try:
                self._encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fall back to cl100k_base for unknown models
                self._encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text

        Args:
            text: Text to count tokens in

        Returns:
            Number of tokens
        """
        if not text:
            return 0

        if self._encoding:
            return len(self._encoding.encode(text))

        # Fallback: approximate
        chars_per_token = self.CHARS_PER_TOKEN.get(self.model, 4.0)
        return int(len(text) / chars_per_token)

    def count_tokens_list(self, texts: List[str]) -> int:
        """Count total tokens in a list of texts"""
        return sum(self.count_tokens(t) for t in texts)

    def count_chat_tokens(self, messages: List[dict]) -> int:
        """
        Count tokens in chat messages

        Accounts for message formatting overhead.

        Args:
            messages: List of chat messages

        Returns:
            Total token count
        """
        # Each message has ~4 tokens of overhead
        overhead_per_message = 4
        total = 0

        for message in messages:
            total += overhead_per_message
            total += self.count_tokens(message.get("role", ""))
            total += self.count_tokens(message.get("content", ""))

        # Additional reply priming
        total += 2

        return total

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed

        Returns:
            Truncated text
        """
        if self.count_tokens(text) <= max_tokens:
            return text

        if self._encoding:
            tokens = self._encoding.encode(text)
            truncated_tokens = tokens[:max_tokens]
            return self._encoding.decode(truncated_tokens)

        # Fallback: character-based truncation
        chars_per_token = self.CHARS_PER_TOKEN.get(self.model, 4.0)
        max_chars = int(max_tokens * chars_per_token)
        return text[:max_chars]

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: Optional[str] = None
    ) -> float:
        """
        Estimate cost in USD

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name (uses instance model if not specified)

        Returns:
            Estimated cost in USD
        """
        model = model or self.model

        # Pricing per 1M tokens (as of 2024)
        pricing = {
            "gpt-4-turbo-preview": {"input": 10.0, "output": 30.0},
            "gpt-4-turbo": {"input": 10.0, "output": 30.0},
            "gpt-4o": {"input": 5.0, "output": 15.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
            "text-embedding-3-large": {"input": 0.13, "output": 0.0},
        }

        model_pricing = pricing.get(model, {"input": 10.0, "output": 30.0})

        input_cost = (input_tokens / 1_000_000) * model_pricing["input"]
        output_cost = (output_tokens / 1_000_000) * model_pricing["output"]

        return input_cost + output_cost

    def split_into_chunks(
        self,
        text: str,
        max_tokens: int,
        overlap_tokens: int = 100
    ) -> List[str]:
        """
        Split text into chunks that fit within token limit

        Args:
            text: Text to split
            max_tokens: Maximum tokens per chunk
            overlap_tokens: Tokens to overlap between chunks

        Returns:
            List of text chunks
        """
        if self.count_tokens(text) <= max_tokens:
            return [text]

        if self._encoding:
            tokens = self._encoding.encode(text)
            chunks = []
            start = 0

            while start < len(tokens):
                end = start + max_tokens
                chunk_tokens = tokens[start:end]
                chunk_text = self._encoding.decode(chunk_tokens)
                chunks.append(chunk_text)
                start = end - overlap_tokens

            return chunks

        # Fallback: character-based chunking
        chars_per_token = self.CHARS_PER_TOKEN.get(self.model, 4.0)
        max_chars = int(max_tokens * chars_per_token)
        overlap_chars = int(overlap_tokens * chars_per_token)

        chunks = []
        start = 0

        while start < len(text):
            end = start + max_chars
            chunks.append(text[start:end])
            start = end - overlap_chars

        return chunks
