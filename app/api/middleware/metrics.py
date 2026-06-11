"""
Prometheus metrics middleware
"""

import time
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


if PROMETHEUS_AVAILABLE:
    # Request metrics
    REQUEST_COUNT = Counter(
        'ai_service_requests_total',
        'Total number of requests',
        ['method', 'path', 'status']
    )

    REQUEST_LATENCY = Histogram(
        'ai_service_request_latency_seconds',
        'Request latency in seconds',
        ['method', 'path'],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
    )

    # Processing metrics
    PROCESSING_COUNT = Counter(
        'ai_service_processing_total',
        'Total number of notice processing jobs',
        ['status']
    )

    PROCESSING_LATENCY = Histogram(
        'ai_service_processing_latency_seconds',
        'Notice processing latency in seconds',
        ['stage'],
        buckets=[1.0, 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0, 180.0]
    )

    # OCR metrics
    OCR_CONFIDENCE = Histogram(
        'ai_service_ocr_confidence',
        'OCR confidence scores',
        ['provider'],
        buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0]
    )

    # Risk score distribution
    RISK_SCORE = Histogram(
        'ai_service_risk_score',
        'Distribution of risk scores',
        buckets=[10, 25, 40, 50, 60, 75, 90, 100]
    )

    # Active processing
    ACTIVE_JOBS = Gauge(
        'ai_service_active_jobs',
        'Number of currently processing jobs'
    )

    # LLM token usage
    LLM_TOKENS = Counter(
        'ai_service_llm_tokens_total',
        'Total LLM tokens used',
        ['type']  # input, output
    )


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware for Prometheus metrics collection

    Tracks:
    - Request counts and latency
    - Processing metrics
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not PROMETHEUS_AVAILABLE:
            return await call_next(request)

        # Handle metrics endpoint
        if request.url.path == "/metrics":
            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST
            )

        # Track request
        method = request.method
        path = self._normalize_path(request.url.path)

        start_time = time.time()

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Record metrics
            REQUEST_COUNT.labels(
                method=method,
                path=path,
                status=response.status_code
            ).inc()

            REQUEST_LATENCY.labels(
                method=method,
                path=path
            ).observe(duration)

            return response

        except Exception as e:
            duration = time.time() - start_time

            REQUEST_COUNT.labels(
                method=method,
                path=path,
                status=500
            ).inc()

            REQUEST_LATENCY.labels(
                method=method,
                path=path
            ).observe(duration)

            raise

    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics labels"""
        # Replace UUIDs with placeholder
        import re
        normalized = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '{id}',
            path,
            flags=re.IGNORECASE
        )
        return normalized


def record_processing_complete(success: bool, stage_timings: dict = None):
    """Record processing completion metrics"""
    if not PROMETHEUS_AVAILABLE:
        return

    PROCESSING_COUNT.labels(
        status="success" if success else "failure"
    ).inc()

    if stage_timings:
        for stage, duration_ms in stage_timings.items():
            PROCESSING_LATENCY.labels(stage=stage).observe(duration_ms / 1000.0)


def record_ocr_confidence(provider: str, confidence: float):
    """Record OCR confidence metric"""
    if PROMETHEUS_AVAILABLE:
        OCR_CONFIDENCE.labels(provider=provider).observe(confidence)


def record_risk_score(score: int):
    """Record risk score metric"""
    if PROMETHEUS_AVAILABLE:
        RISK_SCORE.observe(score)


def record_llm_tokens(input_tokens: int, output_tokens: int):
    """Record LLM token usage"""
    if PROMETHEUS_AVAILABLE:
        LLM_TOKENS.labels(type="input").inc(input_tokens)
        LLM_TOKENS.labels(type="output").inc(output_tokens)


def increment_active_jobs():
    """Increment active jobs gauge"""
    if PROMETHEUS_AVAILABLE:
        ACTIVE_JOBS.inc()


def decrement_active_jobs():
    """Decrement active jobs gauge"""
    if PROMETHEUS_AVAILABLE:
        ACTIVE_JOBS.dec()
