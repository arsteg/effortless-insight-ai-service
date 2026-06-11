"""
Vector store service using pgvector
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
import structlog
from sqlalchemy import select, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import Embedding, SourceType
from app.core.database import get_session_maker

logger = structlog.get_logger()


class VectorStore:
    """
    Vector store using pgvector for similarity search

    Supports:
    - Storing embeddings with metadata
    - Similarity search with filtering
    - Deduplication via content hash
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        self._session = session

    async def _get_session(self) -> AsyncSession:
        """Get database session"""
        if self._session:
            return self._session
        return get_session_maker()()

    async def store(
        self,
        source_type: str,
        source_id: UUID,
        content: str,
        embedding: List[float],
        content_hash: str,
        organization_id: Optional[UUID] = None,
        chunk_index: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """
        Store an embedding in the vector store

        Args:
            source_type: Type of source (notice, gst_rule, etc.)
            source_id: ID of the source document
            content: Text content
            embedding: Embedding vector
            content_hash: Hash for deduplication
            organization_id: Optional organization scope
            chunk_index: Index if content is chunked
            metadata: Additional metadata

        Returns:
            ID of the stored embedding
        """
        async with get_session_maker()() as session:
            # Check for existing embedding with same hash
            existing = await session.execute(
                select(Embedding).where(
                    Embedding.source_id == source_id,
                    Embedding.content_hash == content_hash,
                    Embedding.chunk_index == chunk_index,
                )
            )
            existing_record = existing.scalar_one_or_none()

            if existing_record:
                # Update existing
                existing_record.embedding = embedding
                existing_record.extra_data = metadata or {}
                await session.commit()
                logger.debug(
                    "Updated existing embedding",
                    id=existing_record.id,
                    source_id=source_id
                )
                return existing_record.id

            # Create new embedding
            new_embedding = Embedding(
                source_type=source_type,
                source_id=source_id,
                organization_id=organization_id,
                content_hash=content_hash,
                chunk_index=chunk_index,
                content=content,
                embedding=embedding,
                extra_data=metadata or {},
            )

            session.add(new_embedding)
            await session.commit()
            await session.refresh(new_embedding)

            logger.info(
                "Stored new embedding",
                id=new_embedding.id,
                source_type=source_type,
                source_id=source_id
            )

            return new_embedding.id

    async def search(
        self,
        query_embedding: List[float],
        source_types: Optional[List[str]] = None,
        organization_id: Optional[UUID] = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings

        Args:
            query_embedding: Query embedding vector
            source_types: Filter by source types
            organization_id: Filter by organization
            limit: Maximum results
            min_similarity: Minimum similarity threshold

        Returns:
            List of results with content, metadata, and similarity scores
        """
        async with get_session_maker()() as session:
            # Build query with cosine similarity
            # pgvector uses <=> for cosine distance (1 - similarity)
            similarity_expr = 1 - Embedding.embedding.cosine_distance(query_embedding)

            query = select(
                Embedding.id,
                Embedding.source_type,
                Embedding.source_id,
                Embedding.content,
                Embedding.extra_data,
                similarity_expr.label('similarity')
            ).where(
                similarity_expr >= min_similarity
            )

            # Add filters
            if source_types:
                query = query.where(Embedding.source_type.in_(source_types))

            if organization_id:
                query = query.where(
                    (Embedding.organization_id == organization_id) |
                    (Embedding.organization_id.is_(None))
                )

            # Order by similarity and limit
            query = query.order_by(similarity_expr.desc()).limit(limit)

            result = await session.execute(query)
            rows = result.all()

            return [
                {
                    "id": str(row.id),
                    "source_type": row.source_type,
                    "source_id": str(row.source_id),
                    "content": row.content,
                    "metadata": row.extra_data,
                    "similarity": float(row.similarity),
                }
                for row in rows
            ]

    async def get_by_source(
        self,
        source_type: str,
        source_id: UUID,
    ) -> List[Embedding]:
        """Get all embeddings for a source"""
        async with get_session_maker()() as session:
            result = await session.execute(
                select(Embedding).where(
                    Embedding.source_type == source_type,
                    Embedding.source_id == source_id,
                ).order_by(Embedding.chunk_index)
            )
            return list(result.scalars().all())

    async def delete_by_source(
        self,
        source_type: str,
        source_id: UUID,
    ) -> int:
        """
        Delete all embeddings for a source

        Returns:
            Number of deleted embeddings
        """
        async with get_session_maker()() as session:
            result = await session.execute(
                delete(Embedding).where(
                    Embedding.source_type == source_type,
                    Embedding.source_id == source_id,
                )
            )
            await session.commit()

            count = result.rowcount
            logger.info(
                "Deleted embeddings",
                source_type=source_type,
                source_id=source_id,
                count=count
            )
            return count

    async def count(
        self,
        source_type: Optional[str] = None,
        organization_id: Optional[UUID] = None,
    ) -> int:
        """Count embeddings matching criteria"""
        async with get_session_maker()() as session:
            query = select(func.count(Embedding.id))

            if source_type:
                query = query.where(Embedding.source_type == source_type)

            if organization_id:
                query = query.where(Embedding.organization_id == organization_id)

            result = await session.execute(query)
            return result.scalar_one()

    async def find_similar_notices(
        self,
        notice_id: UUID,
        organization_id: Optional[UUID] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find notices similar to a given notice

        Args:
            notice_id: ID of the notice to find similar to
            organization_id: Scope to organization
            limit: Number of results

        Returns:
            List of similar notices with scores
        """
        async with get_session_maker()() as session:
            # Get the embedding for the source notice
            source_embedding = await session.execute(
                select(Embedding).where(
                    Embedding.source_type == SourceType.NOTICE.value,
                    Embedding.source_id == notice_id,
                    Embedding.chunk_index == 0,  # Main chunk
                )
            )
            source = source_embedding.scalar_one_or_none()

            if not source:
                logger.warning("No embedding found for notice", notice_id=notice_id)
                return []

            # Search for similar
            results = await self.search(
                query_embedding=source.embedding,
                source_types=[SourceType.NOTICE.value],
                organization_id=organization_id,
                limit=limit + 1,  # +1 to exclude self
                min_similarity=0.6,
            )

            # Exclude self and return
            return [
                r for r in results
                if r["source_id"] != str(notice_id)
            ][:limit]
