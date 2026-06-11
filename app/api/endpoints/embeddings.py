"""
Embedding and search endpoints
"""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.schemas.requests import SearchRequest, IndexKnowledgeRequest
from app.schemas.responses import SearchResponse, SearchResult
from app.services.rag.embedding_service import EmbeddingService
from app.services.rag.vector_store import VectorStore
from app.services.rag.knowledge_builder import KnowledgeBuilder

router = APIRouter()
logger = structlog.get_logger()


@router.post("/search", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Semantic search across the knowledge base.

    Searches embedded content using vector similarity to find
    relevant GST rules, circulars, case law, and notice content.

    Request body:
    - query: Search query text
    - sourceType: Optional filter by source type
    - organizationId: Optional scope to organization
    - limit: Number of results (1-50)

    Returns:
    - success: Whether search succeeded
    - query: Original query
    - results: List of matching content with scores
    - total: Total number of results
    """
    logger.info(
        "Semantic search request",
        query=request.query[:50],
        source_type=request.source_type
    )

    try:
        embedding_service = EmbeddingService()
        vector_store = VectorStore()

        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding(request.query)

        # Search
        source_types = [request.source_type] if request.source_type else None
        results = await vector_store.search(
            query_embedding=query_embedding,
            source_types=source_types,
            organization_id=request.organization_id,
            limit=request.limit,
        )

        search_results = [
            SearchResult(
                source_type=r["source_type"],
                source_id=UUID(r["source_id"]),
                content=r["content"][:500],  # Truncate content
                score=r["similarity"],
                metadata=r.get("metadata", {}),
            )
            for r in results
        ]

        return SearchResponse(
            success=True,
            query=request.query,
            results=search_results,
            total=len(search_results)
        )

    except Exception as e:
        logger.error("Semantic search failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index-knowledge")
async def reindex_knowledge_base(
    request: IndexKnowledgeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Reindex knowledge base entries.

    Generates embeddings for knowledge base entries that haven't
    been indexed yet, or forces reindexing of all entries.

    Request body:
    - sourceType: Optional filter to specific source type
    - force: Force reindex even if already indexed

    Returns:
    - success: Whether indexing succeeded
    - indexed: Number of entries indexed
    - failed: Number of entries that failed
    - total: Total entries processed
    """
    logger.info(
        "Knowledge base reindex request",
        source_type=request.source_type,
        force=request.force
    )

    try:
        builder = KnowledgeBuilder()

        result = await builder.reindex_all(
            source_type=request.source_type,
            force=request.force,
        )

        return {
            "success": True,
            "indexed": result["indexed"],
            "failed": result["failed"],
            "total": result["total"],
        }

    except Exception as e:
        logger.error("Knowledge base reindexing failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_embedding_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Get knowledge base and embedding statistics.

    Returns:
    - by_type: Entry counts by source type
    - total_embeddings: Total number of embeddings stored
    """
    try:
        builder = KnowledgeBuilder()
        stats = await builder.get_stats()

        return {
            "success": True,
            **stats
        }

    except Exception as e:
        logger.error("Failed to get stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
