"""
Global error handling middleware
"""

import traceback
from typing import Callable
import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import sentry_sdk

from app.core.config import settings

logger = structlog.get_logger()


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware

    Catches unhandled exceptions and returns proper error responses.
    Also integrates with Sentry for error reporting.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        try:
            return await call_next(request)

        except ValueError as e:
            logger.warning(
                "Value error",
                path=request.url.path,
                error=str(e)
            )
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": str(e),
                    "code": "BAD_REQUEST"
                }
            )

        except PermissionError as e:
            logger.warning(
                "Permission denied",
                path=request.url.path,
                error=str(e)
            )
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "error": "Permission denied",
                    "code": "FORBIDDEN"
                }
            )

        except FileNotFoundError as e:
            logger.warning(
                "Resource not found",
                path=request.url.path,
                error=str(e)
            )
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "Resource not found",
                    "code": "NOT_FOUND"
                }
            )

        except TimeoutError as e:
            logger.error(
                "Request timeout",
                path=request.url.path,
                error=str(e)
            )
            return JSONResponse(
                status_code=408,
                content={
                    "success": False,
                    "error": "Request timeout",
                    "code": "TIMEOUT"
                }
            )

        except Exception as e:
            # Log the error
            request_id = getattr(request.state, 'request_id', 'unknown')
            logger.error(
                "Unhandled exception",
                request_id=request_id,
                path=request.url.path,
                error=str(e),
                traceback=traceback.format_exc()
            )

            # Report to Sentry
            if settings.sentry_dsn:
                sentry_sdk.capture_exception(e)

            # Return error response
            error_message = str(e) if settings.environment == "development" else "Internal server error"

            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": error_message,
                    "code": "INTERNAL_ERROR",
                    "request_id": request_id,
                }
            )


class AIProcessingError(Exception):
    """Custom exception for AI processing errors"""

    def __init__(self, message: str, stage: str = None, notice_id: str = None):
        self.message = message
        self.stage = stage
        self.notice_id = notice_id
        super().__init__(message)


class OCRError(AIProcessingError):
    """OCR processing error"""
    pass


class LLMError(AIProcessingError):
    """LLM processing error"""
    pass


class ValidationError(AIProcessingError):
    """Validation error"""
    pass


class RateLimitError(Exception):
    """Rate limit exceeded"""
    pass
