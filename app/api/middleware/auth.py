"""
API key authentication middleware
"""

from typing import Optional, Callable
from functools import wraps
import structlog
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = structlog.get_logger()

# API key header
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication

    Validates X-API-Key header against configured keys.
    """

    def __init__(self, app, excluded_paths: Optional[list] = None):
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/health",
            "/api/v1/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/",
        ]
        self.api_key = getattr(settings, 'api_key', None)

    async def dispatch(self, request: Request, call_next):
        # Skip authentication for excluded paths
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return await call_next(request)

        # Skip if no API key is configured
        if not self.api_key:
            return await call_next(request)

        # Get API key from header
        provided_key = request.headers.get("X-API-Key")

        if not provided_key:
            logger.warning(
                "Missing API key",
                path=request.url.path,
                client=request.client.host if request.client else "unknown"
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing API key"}
            )

        if provided_key != self.api_key:
            logger.warning(
                "Invalid API key",
                path=request.url.path,
                client=request.client.host if request.client else "unknown"
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key"}
            )

        return await call_next(request)


async def get_api_key(api_key: str = Depends(API_KEY_HEADER)) -> Optional[str]:
    """
    Dependency for API key validation

    Returns the API key if valid, raises HTTPException otherwise.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    expected_key = getattr(settings, 'api_key', None)
    if expected_key and api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key


def require_api_key(func: Callable) -> Callable:
    """
    Decorator for routes that require API key authentication
    """
    @wraps(func)
    async def wrapper(*args, api_key: str = Depends(get_api_key), **kwargs):
        return await func(*args, **kwargs)
    return wrapper
