"""
Embedding management endpoints
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.services.embedding_service import EmbeddingService

router = APIRouter()


class SearchRequest(BaseModel):
    """Request model for semantic search"""
    query: str
    source_type: str | None = None  # notice, gst_rule, circular, case_law
    limit: int = 10


@router.post("/search")
async def semantic_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Perform semantic search across knowledge base"""
    embedding_service = EmbeddingService()
    results = await embedding_service.search(
        query=request.query,
        source_type=request.source_type,
        limit=request.limit
    )
    return {"results": results}


@router.post("/index-knowledge")
async def index_knowledge_base(
    db: AsyncSession = Depends(get_db)
):
    """Trigger re-indexing of knowledge base (admin only)"""
    embedding_service = EmbeddingService()
    count = await embedding_service.reindex_knowledge_base()
    return {"indexed_count": count}
