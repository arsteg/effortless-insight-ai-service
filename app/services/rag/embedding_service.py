"""
Embedding service using OpenAI
"""

import hashlib
from typing import List, Optional
import structlog
from openai import AsyncOpenAI

from app.core.config import settings

logger = structlog.get_logger()


class EmbeddingService:
    """
    Service for generating embeddings using OpenAI

    Uses text-embedding-3-large (3072 dimensions)
    """

    # Maximum tokens per embedding request
    MAX_TOKENS = 8191

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model
        self.dimension = 3072  # text-embedding-3-large dimension

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text

        Args:
            text: Text to embed (will be truncated if too long)

        Returns:
            Embedding vector (3072 dimensions)
        """
        try:
            # Truncate if necessary
            text = self._truncate_text(text)

            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )

            return response.data[0].embedding

        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            raise

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call

        Returns:
            List of embedding vectors
        """
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch = [self._truncate_text(t) for t in batch]

            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )

                for item in response.data:
                    embeddings.append(item.embedding)

            except Exception as e:
                logger.error(
                    "Batch embedding generation failed",
                    batch_start=i,
                    error=str(e)
                )
                raise

        return embeddings

    def _truncate_text(self, text: str, max_chars: int = 30000) -> str:
        """
        Truncate text to fit within token limits

        Uses character count as approximation (4 chars ≈ 1 token)
        """
        if len(text) <= max_chars:
            return text

        # Truncate and add indicator
        truncated = text[:max_chars - 50] + "... [truncated]"
        logger.warning(
            "Text truncated for embedding",
            original_length=len(text),
            truncated_length=len(truncated)
        )
        return truncated

    def get_content_hash(self, text: str) -> str:
        """
        Get SHA-256 hash of text for deduplication

        Args:
            text: Text to hash

        Returns:
            64-character hex hash
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> List[str]:
        """
        Split text into overlapping chunks for embedding

        Args:
            text: Text to chunk
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end
                for punct in ['. ', '.\n', '? ', '?\n', '! ', '!\n']:
                    last_punct = text[start:end].rfind(punct)
                    if last_punct > chunk_size // 2:
                        end = start + last_punct + len(punct)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    async def is_available(self) -> bool:
        """Check if embedding service is available"""
        try:
            # Try a minimal embedding request
            await self.client.embeddings.create(
                model=self.model,
                input="test"
            )
            return True
        except Exception:
            return False
