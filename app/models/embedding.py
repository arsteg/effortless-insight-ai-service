"""
Embedding model for pgvector storage
"""

from enum import Enum
from sqlalchemy import Column, String, Text, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin, UUIDMixin


class SourceType(str, Enum):
    """Types of content that can be embedded"""
    NOTICE = "notice"
    GST_RULE = "gst_rule"
    CIRCULAR = "circular"
    CASE_LAW = "case_law"
    TEMPLATE = "template"


class Embedding(Base, UUIDMixin, TimestampMixin):
    """
    Embedding model for vector similarity search using pgvector

    This stores embeddings for notices and knowledge base entries
    to enable semantic search and RAG retrieval.
    """
    __tablename__ = "embeddings"

    # Source information
    source_type = Column(String(50), nullable=False, index=True)
    source_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Content deduplication
    content_hash = Column(String(64), nullable=False, index=True)
    chunk_index = Column(Integer, default=0, nullable=False)

    # Content
    content = Column(Text, nullable=False)

    # Vector embedding (3072 dimensions for text-embedding-3-large)
    embedding = Column(Vector(3072), nullable=False)

    # Additional metadata (named extra_data to avoid SQLAlchemy reserved name)
    extra_data = Column("metadata", JSONB, default=dict, nullable=False)

    __table_args__ = (
        # HNSW index for fast approximate nearest neighbor search
        Index(
            'ix_embeddings_embedding_hnsw',
            embedding,
            postgresql_using='hnsw',
            postgresql_with={'m': 16, 'ef_construction': 64},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
        # Composite index for source lookup
        Index('ix_embeddings_source', 'source_type', 'source_id'),
        # Composite index for organization-scoped search
        Index('ix_embeddings_org_source', 'organization_id', 'source_type'),
    )

    def __repr__(self) -> str:
        return f"<Embedding(id={self.id}, source_type={self.source_type}, source_id={self.source_id})>"
