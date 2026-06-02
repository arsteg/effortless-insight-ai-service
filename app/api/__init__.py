"""
API Router
"""

from fastapi import APIRouter
from app.api.endpoints import process, embeddings, health

router = APIRouter()

router.include_router(process.router, prefix="/process", tags=["Processing"])
router.include_router(embeddings.router, prefix="/embeddings", tags=["Embeddings"])
router.include_router(health.router, prefix="/health", tags=["Health"])
