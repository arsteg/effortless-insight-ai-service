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
    """Initialize database connection"""
    engine = get_engine()
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


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
