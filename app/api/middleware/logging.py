"""
Request logging middleware
"""

import time
import uuid
from typing import Callable
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured request logging

    Logs:
    - Request start
    - Request completion with timing
    - Errors
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Extract request info
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        query = str(request.query_params) if request.query_params else ""

        # Start timing
        start_time = time.time()

        # Log request start
        logger.info(
            "Request started",
            request_id=request_id,
            method=method,
            path=path,
            query=query,
            client_ip=client_ip,
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log completion
            logger.info(
                "Request completed",
                request_id=request_id,
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log error
            logger.error(
                "Request failed",
                request_id=request_id,
                method=method,
                path=path,
                error=str(e),
                duration_ms=duration_ms,
            )

            raise


def get_request_id(request: Request) -> str:
    """Get request ID from request state"""
    return getattr(request.state, 'request_id', 'unknown')
