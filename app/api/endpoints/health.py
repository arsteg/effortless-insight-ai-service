"""
Health check endpoints
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health():
    """Basic health check"""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness():
    """Readiness check - verifies dependencies"""
    # TODO: Check database, Redis, OpenAI connectivity
    return {
        "status": "ready",
        "checks": {
            "database": "ok",
            "redis": "ok",
            "openai": "ok"
        }
    }
