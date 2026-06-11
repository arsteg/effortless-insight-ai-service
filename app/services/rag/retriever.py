"""
RAG retriever for context retrieval
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
import structlog

from app.services.rag.embedding_service import EmbeddingService
from app.services.rag.vector_store import VectorStore
from app.schemas.internal import RAGContext

logger = structlog.get_logger()


class RAGRetriever:
    """
    RAG retriever for fetching relevant context

    Retrieves:
    - GST rules and sections
    - Circulars and notifications
    - Case law
    - Response templates
    """

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()

    async def retrieve_context(
        self,
        query: str,
        notice_type: Optional[str] = None,
        top_k: int = 10,
        organization_id: Optional[UUID] = None,
    ) -> RAGContext:
        """
        Retrieve relevant context for a query

        Args:
            query: Query text (usually notice content)
            notice_type: Type of notice for filtering
            top_k: Number of results per source type
            organization_id: Optional organization scope

        Returns:
            RAGContext with retrieved information
        """
        logger.info(
            "Retrieving RAG context",
            query_length=len(query),
            notice_type=notice_type,
            top_k=top_k
        )

        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query)

            # Retrieve from different sources
            gst_rules = await self._retrieve_gst_rules(query_embedding, top_k)
            circulars = await self._retrieve_circulars(query_embedding, top_k // 2)
            case_laws = await self._retrieve_case_laws(query_embedding, top_k // 2)
            templates = await self._retrieve_templates(query_embedding, notice_type)

            # Rerank and deduplicate
            all_contexts = gst_rules + circulars + case_laws + templates
            ranked_contexts = self._rerank_results(all_contexts, query)

            # Extract text content
            gst_rule_texts = [c["content"] for c in ranked_contexts if c["source_type"] == "gst_rule"][:top_k]
            circular_texts = [c["content"] for c in ranked_contexts if c["source_type"] == "circular"][:5]
            case_law_texts = [c["content"] for c in ranked_contexts if c["source_type"] == "case_law"][:5]
            template_texts = [c["content"] for c in ranked_contexts if c["source_type"] == "template"][:3]

            logger.info(
                "RAG context retrieved",
                rules=len(gst_rule_texts),
                circulars=len(circular_texts),
                case_laws=len(case_law_texts),
                templates=len(template_texts)
            )

            return RAGContext(
                success=True,
                contexts=ranked_contexts[:top_k],
                total_retrieved=len(all_contexts),
                gst_rules=gst_rule_texts,
                circulars=circular_texts,
                case_laws=case_law_texts,
                templates=template_texts,
            )

        except Exception as e:
            logger.error("RAG retrieval failed", error=str(e))
            return RAGContext(
                success=False,
                error=str(e),
            )

    async def _retrieve_gst_rules(
        self,
        query_embedding: List[float],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant GST rules and sections"""
        return await self.vector_store.search(
            query_embedding=query_embedding,
            source_types=["gst_rule", "gst_section"],
            limit=limit,
            min_similarity=0.5,
        )

    async def _retrieve_circulars(
        self,
        query_embedding: List[float],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant circulars and notifications"""
        return await self.vector_store.search(
            query_embedding=query_embedding,
            source_types=["circular", "notification"],
            limit=limit,
            min_similarity=0.5,
        )

    async def _retrieve_case_laws(
        self,
        query_embedding: List[float],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant case law"""
        return await self.vector_store.search(
            query_embedding=query_embedding,
            source_types=["case_law"],
            limit=limit,
            min_similarity=0.55,
        )

    async def _retrieve_templates(
        self,
        query_embedding: List[float],
        notice_type: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant response templates"""
        results = await self.vector_store.search(
            query_embedding=query_embedding,
            source_types=["template"],
            limit=5,
            min_similarity=0.6,
        )

        # Filter by notice type if provided
        if notice_type:
            filtered = [
                r for r in results
                if notice_type.upper() in str(r.get("metadata", {}).get("notice_types", [])).upper()
            ]
            if filtered:
                return filtered

        return results

    def _rerank_results(
        self,
        results: List[Dict[str, Any]],
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Rerank results based on relevance

        Simple reranking based on:
        - Original similarity score
        - Keyword overlap
        - Source type priority
        """
        # Source type weights
        source_weights = {
            "gst_rule": 1.2,
            "gst_section": 1.2,
            "circular": 1.0,
            "notification": 1.0,
            "case_law": 0.9,
            "template": 0.8,
        }

        # Extract keywords from query
        import re
        query_words = set(re.findall(r'\b\w{4,}\b', query.lower()))

        for result in results:
            content_words = set(re.findall(r'\b\w{4,}\b', result.get("content", "").lower()))
            keyword_overlap = len(query_words & content_words) / max(len(query_words), 1)

            # Calculate reranked score
            base_score = result.get("similarity", 0.5)
            source_weight = source_weights.get(result.get("source_type", ""), 1.0)
            keyword_boost = keyword_overlap * 0.2

            result["reranked_score"] = base_score * source_weight + keyword_boost

        # Sort by reranked score
        return sorted(results, key=lambda x: x.get("reranked_score", 0), reverse=True)

    async def retrieve_for_notice(
        self,
        notice_text: str,
        notice_type: Optional[str] = None,
        sections: Optional[List[str]] = None,
        organization_id: Optional[UUID] = None,
    ) -> RAGContext:
        """
        Retrieve context specifically for notice analysis

        Args:
            notice_text: Full notice text
            notice_type: Type of notice
            sections: Section references found in notice
            organization_id: Organization scope

        Returns:
            RAGContext with relevant information
        """
        # Build enhanced query
        query_parts = [notice_text[:3000]]  # Truncate notice

        if sections:
            query_parts.extend([f"GST {s}" for s in sections[:5]])

        if notice_type:
            query_parts.append(f"Notice type {notice_type}")

        enhanced_query = " ".join(query_parts)

        return await self.retrieve_context(
            query=enhanced_query,
            notice_type=notice_type,
            top_k=10,
            organization_id=organization_id,
        )

    def format_context_for_prompt(
        self,
        rag_context: RAGContext,
        max_length: int = 4000,
    ) -> str:
        """
        Format RAG context for inclusion in LLM prompt

        Args:
            rag_context: Retrieved context
            max_length: Maximum length in characters

        Returns:
            Formatted context string
        """
        parts = []

        if rag_context.gst_rules:
            parts.append("## Relevant GST Rules and Sections:")
            for rule in rag_context.gst_rules[:3]:
                parts.append(f"- {rule[:500]}")

        if rag_context.circulars:
            parts.append("\n## Relevant Circulars:")
            for circular in rag_context.circulars[:2]:
                parts.append(f"- {circular[:400]}")

        if rag_context.case_laws:
            parts.append("\n## Relevant Case Law:")
            for case in rag_context.case_laws[:2]:
                parts.append(f"- {case[:400]}")

        formatted = "\n".join(parts)

        if len(formatted) > max_length:
            formatted = formatted[:max_length - 50] + "\n... [truncated]"

        return formatted
