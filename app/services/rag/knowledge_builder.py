"""
Knowledge base builder for RAG
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBaseEntry
from app.services.rag.embedding_service import EmbeddingService
from app.services.rag.vector_store import VectorStore
from app.core.database import get_session_maker

logger = structlog.get_logger()


class KnowledgeBuilder:
    """
    Knowledge base builder for ingesting and indexing documents

    Handles:
    - GST rules and sections
    - Circulars and notifications
    - Case law
    - Response templates
    """

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()

    async def index_entry(
        self,
        entry: KnowledgeBaseEntry,
        force: bool = False,
    ) -> bool:
        """
        Index a knowledge base entry

        Args:
            entry: Knowledge base entry to index
            force: Force reindex even if already indexed

        Returns:
            True if indexed successfully
        """
        if entry.is_indexed and not force:
            logger.debug("Entry already indexed", entry_id=entry.id)
            return True

        try:
            # Combine title and content for embedding
            text = f"{entry.title}\n\n{entry.content}"
            if entry.summary:
                text = f"{entry.summary}\n\n{text}"

            # Check if content needs chunking
            chunks = self.embedding_service.chunk_text(text)

            for i, chunk in enumerate(chunks):
                # Generate embedding
                embedding = await self.embedding_service.generate_embedding(chunk)
                content_hash = self.embedding_service.get_content_hash(chunk)

                # Build metadata
                metadata = {
                    "reference": entry.reference,
                    "title": entry.title,
                    "source_type": entry.source_type,
                    "keywords": entry.keywords,
                    "categories": entry.categories,
                    "effective_date": str(entry.effective_date) if entry.effective_date else None,
                    "authority": entry.authority,
                    "related_sections": entry.related_sections,
                }

                # Store embedding
                await self.vector_store.store(
                    source_type=entry.source_type,
                    source_id=entry.id,
                    content=chunk,
                    embedding=embedding,
                    content_hash=content_hash,
                    chunk_index=i,
                    metadata=metadata,
                )

            # Mark as indexed
            async with get_session_maker()() as session:
                entry_db = await session.get(KnowledgeBaseEntry, entry.id)
                if entry_db:
                    entry_db.is_indexed = True
                    await session.commit()

            logger.info(
                "Entry indexed",
                entry_id=entry.id,
                reference=entry.reference,
                chunks=len(chunks)
            )
            return True

        except Exception as e:
            logger.error("Failed to index entry", entry_id=entry.id, error=str(e))
            return False

    async def reindex_all(
        self,
        source_type: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, int]:
        """
        Reindex all knowledge base entries

        Args:
            source_type: Only reindex specific type
            force: Force reindex even if already indexed

        Returns:
            Dict with counts of indexed and failed entries
        """
        async with get_session_maker()() as session:
            query = select(KnowledgeBaseEntry).where(
                KnowledgeBaseEntry.is_active == True
            )

            if source_type:
                query = query.where(KnowledgeBaseEntry.source_type == source_type)

            if not force:
                query = query.where(KnowledgeBaseEntry.is_indexed == False)

            result = await session.execute(query)
            entries = list(result.scalars().all())

        indexed = 0
        failed = 0

        for entry in entries:
            success = await self.index_entry(entry, force=force)
            if success:
                indexed += 1
            else:
                failed += 1

        logger.info(
            "Reindexing complete",
            source_type=source_type,
            indexed=indexed,
            failed=failed
        )

        return {
            "indexed": indexed,
            "failed": failed,
            "total": len(entries),
        }

    async def add_entry(
        self,
        source_type: str,
        reference: str,
        title: str,
        content: str,
        summary: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_index: bool = True,
    ) -> KnowledgeBaseEntry:
        """
        Add a new knowledge base entry

        Args:
            source_type: Type of knowledge (gst_rule, circular, etc.)
            reference: Unique reference (e.g., "Section 73")
            title: Entry title
            content: Full content
            summary: Optional summary
            keywords: Search keywords
            categories: Categories
            metadata: Additional metadata
            auto_index: Automatically index after creation

        Returns:
            Created entry
        """
        async with get_session_maker()() as session:
            entry = KnowledgeBaseEntry(
                source_type=source_type,
                reference=reference,
                title=title,
                content=content,
                summary=summary,
                keywords=keywords or [],
                categories=categories or [],
                metadata=metadata or {},
                is_active=True,
                is_indexed=False,
            )

            session.add(entry)
            await session.commit()
            await session.refresh(entry)

            logger.info(
                "Knowledge entry created",
                entry_id=entry.id,
                reference=reference,
                source_type=source_type
            )

            if auto_index:
                await self.index_entry(entry)

            return entry

    async def delete_entry(self, entry_id: UUID) -> bool:
        """
        Delete a knowledge base entry and its embeddings

        Args:
            entry_id: ID of entry to delete

        Returns:
            True if deleted
        """
        async with get_session_maker()() as session:
            entry = await session.get(KnowledgeBaseEntry, entry_id)
            if not entry:
                return False

            # Delete embeddings
            await self.vector_store.delete_by_source(
                source_type=entry.source_type,
                source_id=entry_id,
            )

            # Delete entry
            await session.delete(entry)
            await session.commit()

            logger.info("Knowledge entry deleted", entry_id=entry_id)
            return True

    async def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        async with get_session_maker()() as session:
            # Count by source type
            from sqlalchemy import func

            result = await session.execute(
                select(
                    KnowledgeBaseEntry.source_type,
                    func.count(KnowledgeBaseEntry.id).label('count'),
                    func.sum(
                        func.case((KnowledgeBaseEntry.is_indexed == True, 1), else_=0)
                    ).label('indexed')
                ).where(
                    KnowledgeBaseEntry.is_active == True
                ).group_by(
                    KnowledgeBaseEntry.source_type
                )
            )

            stats_by_type = {
                row.source_type: {
                    "total": row.count,
                    "indexed": row.indexed or 0,
                }
                for row in result.all()
            }

            # Count total embeddings
            embedding_count = await self.vector_store.count()

            return {
                "by_type": stats_by_type,
                "total_embeddings": embedding_count,
            }

    async def seed_gst_sections(self, sections: List[Dict[str, Any]]) -> int:
        """
        Seed GST sections into knowledge base

        Args:
            sections: List of section dicts with reference, title, content

        Returns:
            Number of sections added
        """
        count = 0
        for section in sections:
            try:
                await self.add_entry(
                    source_type="gst_section",
                    reference=section["reference"],
                    title=section["title"],
                    content=section["content"],
                    summary=section.get("summary"),
                    keywords=section.get("keywords", []),
                    categories=["CGST Act", "GST Law"],
                    auto_index=True,
                )
                count += 1
            except Exception as e:
                logger.error(
                    "Failed to seed section",
                    reference=section.get("reference"),
                    error=str(e)
                )

        return count
