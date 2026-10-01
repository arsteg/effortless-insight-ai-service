"""
Product-knowledge retrieval for the assistant (RAG over product_guide entries).
"""

from typing import List, Tuple

import structlog

from app.core.config import settings
from app.services.rag.embedding_service import EmbeddingService
from app.services.rag.vector_store import VectorStore

logger = structlog.get_logger()

# Product guidance is global knowledge; FAQ/PROCEDURE entries are included
# so future curated help content surfaces too. Notice-analysis sources
# (gst_rule, case_law, ...) are intentionally excluded here.
ASSISTANT_SOURCE_TYPES = ["product_guide", "faq", "procedure"]


class ProductKnowledgeRetriever:
    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()

    async def retrieve(self, query: str) -> Tuple[List[str], List[str]]:
        """
        Retrieve relevant product-knowledge chunks for a user question.

        Returns (knowledge_blocks, citations) where each block is prefixed
        with its reference, and citations is the ordered unique reference list.
        """
        try:
            query_embedding = await self.embedding_service.generate_embedding(query)
            results = await self.vector_store.search(
                query_embedding=query_embedding,
                source_types=ASSISTANT_SOURCE_TYPES,
                limit=settings.assistant_rag_top_k,
                min_similarity=settings.assistant_rag_min_similarity,
            )
        except Exception as exc:
            # Retrieval failure degrades to "answer from safety-net prompt only"
            logger.warning("Assistant knowledge retrieval failed", error=str(exc))
            return [], []

        blocks: List[str] = []
        citations: List[str] = []
        for result in results:
            metadata = result.get("metadata") or {}
            reference = metadata.get("reference", "")
            title = metadata.get("title", "")
            content = result.get("content", "")
            blocks.append(f"[{reference}] {title}\n{content}")
            if reference and reference not in citations:
                citations.append(reference)

        return blocks, citations
