"""
Database configuration and connection management
"""

from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from app.core.config import settings

# Base class for models
Base = declarative_base()

# Lazy-initialized engine and session maker
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker] = None


def get_engine() -> AsyncEngine:
    """Get or create the database engine (lazy initialization)"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.environment == "development",
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_session_maker() -> async_sessionmaker:
    """Get or create the session maker (lazy initialization)"""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_maker


async def init_db():
    """Initialize database connection and create tables"""
    engine = get_engine()
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Create embeddings table if it doesn't exist
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_type VARCHAR(50) NOT NULL,
                source_id UUID NOT NULL,
                organization_id UUID,
                content_hash VARCHAR(64) NOT NULL,
                chunk_index INTEGER NOT NULL DEFAULT 0,
                content TEXT NOT NULL,
                embedding vector(3072) NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        # Create indexes if they don't exist
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_embeddings_source_type ON embeddings(source_type)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_embeddings_source_id ON embeddings(source_id)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_embeddings_organization_id ON embeddings(organization_id)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_embeddings_content_hash ON embeddings(content_hash)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_embeddings_source ON embeddings(source_type, source_id)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_embeddings_org_source ON embeddings(organization_id, source_type)
        """))

        # Note: Skipping vector index creation because:
        # - HNSW and IVFFlat have a 2000 dimension limit in pgvector
        # - text-embedding-3-large produces 3072 dimensions
        # - For small knowledge bases (<1000 entries), exact search is fast enough
        # - If scaling up, consider using text-embedding-3-small (1536 dims) instead

        # Create knowledge_base_entries table if it doesn't exist
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS knowledge_base_entries (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_type VARCHAR(50) NOT NULL,
                reference VARCHAR(255) NOT NULL UNIQUE,
                title VARCHAR(500) NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                effective_date DATE,
                expiry_date DATE,
                authority VARCHAR(255),
                keywords TEXT[] NOT NULL DEFAULT '{}',
                categories TEXT[] NOT NULL DEFAULT '{}',
                related_sections TEXT[] NOT NULL DEFAULT '{}',
                related_rules TEXT[] NOT NULL DEFAULT '{}',
                supersedes VARCHAR(255),
                metadata JSONB NOT NULL DEFAULT '{}',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_indexed BOOLEAN NOT NULL DEFAULT FALSE,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        # Create indexes for knowledge_base_entries
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_kb_source_type ON knowledge_base_entries(source_type)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_kb_is_active ON knowledge_base_entries(is_active)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_kb_is_indexed ON knowledge_base_entries(is_indexed)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_kb_source_active ON knowledge_base_entries(source_type, is_active)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_kb_reference ON knowledge_base_entries(reference)
        """))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
