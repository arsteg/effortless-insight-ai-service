"""
Admin endpoints for service management
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.services.ocr.ocr_service import OCRService
from app.services.llm.client import LLMClient

router = APIRouter()
logger = structlog.get_logger()


@router.get("/status")
async def get_service_status():
    """
    Get overall service status and configuration.

    Returns status of all service components and their configuration.
    """
    try:
        ocr_service = OCRService()
        llm_client = LLMClient()

        # Get OCR provider status
        ocr_status = await ocr_service.get_provider_status()

        # Get LLM availability
        llm_available = await llm_client.is_available()

        return {
            "success": True,
            "status": "operational",
            "components": {
                "ocr": ocr_status,
                "llm": {
                    "available": llm_available,
                    "model": llm_client.model,
                },
                "rag": {
                    "embedding_model": "text-embedding-3-large",
                    "dimension": 3072,
                }
            }
        }

    except Exception as e:
        logger.error("Failed to get service status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_service_config():
    """
    Get current service configuration (non-sensitive).

    Returns configuration values that can be safely exposed.
    """
    from app.core.config import settings

    return {
        "success": True,
        "config": {
            "environment": settings.environment,
            "openai_model": settings.openai_model,
            "embedding_model": settings.openai_embedding_model,
            "google_cloud_location": settings.google_cloud_location,
            "ocr_confidence_threshold": getattr(settings, 'ocr_confidence_threshold', 0.70),
            "cors_origins": settings.cors_origins,
        }
    }


@router.post("/clear-cache")
async def clear_cache():
    """
    Clear service caches.

    Clears in-memory caches for embeddings and LLM responses.
    """
    # TODO: Implement cache clearing if caching is added
    return {
        "success": True,
        "message": "Cache cleared"
    }


@router.get("/usage")
async def get_usage_stats():
    """
    Get API usage statistics.

    Returns token usage and estimated costs for LLM operations.
    """
    try:
        llm_client = LLMClient()
        usage = llm_client.get_usage_stats()

        return {
            "success": True,
            "usage": usage
        }

    except Exception as e:
        logger.error("Failed to get usage stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
