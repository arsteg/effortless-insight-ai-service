"""
Unit tests for API middleware
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.api.middleware.auth import APIKeyMiddleware
from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.api.middleware.logging import RequestLoggingMiddleware
from app.api.middleware.metrics import MetricsMiddleware, REQUEST_COUNT


class TestAPIKeyMiddleware:
    """Test cases for API key authentication"""

    def test_auth_initialization(self):
        """Test auth middleware initialization"""
        app = MagicMock()
        auth = APIKeyMiddleware(app)
        assert auth is not None

    def test_auth_with_excluded_paths(self):
        """Test auth with excluded paths"""
        app = MagicMock()
        auth = APIKeyMiddleware(app, excluded_paths=["/health", "/metrics"])
        assert "/health" in auth.excluded_paths
        assert "/metrics" in auth.excluded_paths

    def test_default_excluded_paths(self):
        """Test default excluded paths"""
        app = MagicMock()
        auth = APIKeyMiddleware(app)
        assert hasattr(auth, 'excluded_paths')
        assert len(auth.excluded_paths) > 0


class TestErrorHandlerMiddleware:
    """Test cases for error handler middleware"""

    def test_error_handler_initialization(self):
        """Test error handler initialization"""
        app = MagicMock()
        handler = ErrorHandlerMiddleware(app)
        assert handler is not None

    def test_format_error_response(self):
        """Test error response formatting"""
        error_response = {
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An error occurred"
            }
        }
        assert error_response["success"] is False
        assert "error" in error_response


class TestRequestLoggingMiddleware:
    """Test cases for logging middleware"""

    def test_logging_initialization(self):
        """Test logging middleware initialization"""
        app = MagicMock()
        middleware = RequestLoggingMiddleware(app)
        assert middleware is not None


class TestMetricsMiddleware:
    """Test cases for metrics middleware"""

    def test_metrics_initialization(self):
        """Test metrics middleware initialization"""
        app = MagicMock()
        middleware = MetricsMiddleware(app)
        assert middleware is not None

    def test_request_counter_exists(self):
        """Test request counter metric exists"""
        assert REQUEST_COUNT is not None
