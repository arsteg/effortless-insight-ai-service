"""
API router configuration
"""

from fastapi import APIRouter

from app.api.endpoints import health, process, embeddings, admin

router = APIRouter()

# Include endpoint routers
router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(process.router, prefix="/process", tags=["Processing"])
router.include_router(embeddings.router, prefix="/embeddings", tags=["Embeddings"])
router.include_router(admin.router, prefix="/admin", tags=["Admin"])
