"""
Health check endpoints
"""

from fastapi import APIRouter
import structlog

from app.core.config import settings
from app.core.database import get_session_maker
from app.schemas.responses import HealthResponse, ReadinessResponse, HealthCheck

router = APIRouter()
logger = structlog.get_logger()


@router.get("", response_model=HealthResponse)
async def health():
    """
    Basic health check endpoint.

    Returns service status without checking dependencies.
    Use /ready for full readiness check.
    """
    return HealthResponse(
        status="healthy",
        service="ai-service",
        version="1.0.0"
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness():
    """
    Readiness check - verifies all dependencies are accessible.

    Checks:
    - Database connectivity
    - Redis connectivity (if configured)
    - OpenAI API availability

    Returns detailed status for each dependency.
    """
    checks = {}
    overall_status = "ready"

    # Check database
    db_check = await _check_database()
    checks["database"] = db_check
    if db_check.status != "ok":
        overall_status = "not_ready"

    # Check Redis
    redis_check = await _check_redis()
    checks["redis"] = redis_check
    if redis_check.status == "error":
        # Redis is optional, just warn
        pass

    # Check OpenAI
    openai_check = await _check_openai()
    checks["openai"] = openai_check
    if openai_check.status != "ok":
        overall_status = "not_ready"

    return ReadinessResponse(
        status=overall_status,
        checks=checks
    )


async def _check_database() -> HealthCheck:
    """Check database connectivity"""
    import time
    start = time.time()

    try:
        async with get_session_maker()() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))

        latency = int((time.time() - start) * 1000)
        return HealthCheck(
            status="ok",
            latency_ms=latency
        )

    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return HealthCheck(
            status="error",
            message=str(e)
        )


async def _check_redis() -> HealthCheck:
    """Check Redis connectivity"""
    import time
    start = time.time()

    try:
        import redis.asyncio as redis
        client = redis.from_url(settings.redis_url)
        await client.ping()
        await client.close()

        latency = int((time.time() - start) * 1000)
        return HealthCheck(
            status="ok",
            latency_ms=latency
        )

    except Exception as e:
        logger.warning("Redis health check failed", error=str(e))
        return HealthCheck(
            status="degraded",
            message="Redis not available"
        )


async def _check_openai() -> HealthCheck:
    """Check OpenAI API availability"""
    import time
    start = time.time()

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        await client.models.retrieve(settings.openai_model)

        latency = int((time.time() - start) * 1000)
        return HealthCheck(
            status="ok",
            latency_ms=latency
        )

    except Exception as e:
        logger.error("OpenAI health check failed", error=str(e))
        return HealthCheck(
            status="error",
            message="OpenAI API not accessible"
        )
