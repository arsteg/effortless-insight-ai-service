"""
EffortlessInsight AI Service
FastAPI application for AI-powered notice processing
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
import structlog

from app.core.config import settings
from app.core.log_config import setup_logging
from app.api import router as api_router
from app.api.middleware.auth import APIKeyMiddleware
from app.api.middleware.logging import RequestLoggingMiddleware
from app.api.middleware.metrics import MetricsMiddleware
from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.core.database import init_db

# Setup logging
setup_logging()
logger = structlog.get_logger()

# Initialize Sentry
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting EffortlessInsight AI Service")

    # Initialize database connection
    await init_db()

    yield

    logger.info("Shutting down EffortlessInsight AI Service")


# Create FastAPI application
app = FastAPI(
    title="EffortlessInsight AI Service",
    description="AI-powered GST notice processing service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
)

# Add middleware (order matters - first added = outermost)
# Error handler should be outermost to catch all errors
app.add_middleware(ErrorHandlerMiddleware)

# Metrics middleware for request timing
app.add_middleware(MetricsMiddleware)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# API key authentication (after logging so we log auth failures)
app.add_middleware(APIKeyMiddleware)

# CORS middleware (innermost for preflight handling)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ai-service"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "EffortlessInsight AI Service",
        "version": "1.0.0",
        "status": "running"
    }
