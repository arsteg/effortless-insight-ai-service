"""
Application configuration using Pydantic Settings
"""

import os
from typing import Optional, List, Dict
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""

    # Environment
    environment: str = "development"

    # API Security
    api_key: Optional[str] = None  # API key for service authentication

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/effortlessinsight"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # OpenAI
    openai_api_key: str = ""  # Required: Set via OPENAI_API_KEY environment variable
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-large"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096

    # Google Cloud (Primary OCR)
    google_cloud_project_id: str = ""
    google_cloud_location: str = "us"
    google_document_ai_processor_id: str = ""
    google_application_credentials: str = ""  # Path to service account JSON file

    # Azure Form Recognizer (Fallback OCR)
    azure_form_recognizer_endpoint: str = ""
    azure_form_recognizer_key: str = ""

    # OCR Settings
    ocr_confidence_threshold: float = 0.70
    ocr_language_hints: List[str] = ["en", "hi"]

    # Vision-LLM extraction (multimodal model reads page images directly,
    # recovering handwriting, Hindi text and reading order that OCR loses)
    vision_extraction_enabled: bool = True
    vision_model: str = ""  # blank = use openai_model
    vision_max_pages: int = 10
    vision_dpi: int = 200
    # Windows dev: pdf2image needs poppler; point this at poppler's bin folder
    # if it is not on PATH (Docker installs poppler-utils system-wide)
    poppler_path: str = ""

    # LLM analysis input limit (characters of notice text sent to the analyzer)
    analysis_max_chars: int = 60000

    # AWS
    aws_region: str = "ap-south-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = "effortlessinsight-uploads"

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5000"]

    # Monitoring
    sentry_dsn: Optional[str] = None

    # API Service (for callbacks)
    api_service_url: str = "http://localhost:5000"

    # RAG Settings
    rag_top_k: int = 10
    rag_min_similarity: float = 0.5

    # Pipeline Settings
    pipeline_timeout_seconds: int = 180

    # Rate Limiting (short-term burst protection on cost-incurring endpoints)
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds
    # If the Redis counter store is unreachable, allow the request through
    # (True) rather than failing it. Paired with the absolute monthly ceiling
    # below so fail-open can never mean fail-unbounded.
    rate_limit_fail_open: bool = True

    # Per-plan monthly usage caps — the number of cost-incurring AI *requests*
    # (process + generate-response + similar) an organization may make per
    # calendar month. The caller's plan arrives in the `X-Plan` header and the
    # org in `X-Organization-Id`, both set by the .NET API. A value of 0 = "unlimited".
    #
    # IMPORTANT: the .NET API is the AUTHORITATIVE per-plan gate — it blocks by
    # monthly *notice* count (PlanSeeder: free=10, starter=50, professional=200,
    # enterprise=unlimited) before it ever calls this service. These caps are a
    # defense-in-depth BACKSTOP, so they are set ~5x the notice quota to leave
    # headroom for the several AI calls a single notice can trigger; they must
    # not be tighter than the notice quota or they would false-block.
    usage_caps_enabled: bool = True
    plan_monthly_request_caps: Dict[str, int] = {
        "free": 50,
        "starter": 250,
        "professional": 1000,
        "enterprise": 0,   # 0 = unlimited
        "default": 50,     # used when no/unknown plan is supplied (treat as free)
    }
    # Absolute per-organization monthly ceiling enforced regardless of plan —
    # a wallet circuit-breaker / defense-in-depth backstop. 0 = disabled.
    usage_global_org_monthly_cap: int = 5000

    class Config:
        env_file = ".env"
        case_sensitive = False
        # Tolerate legacy/unknown keys in .env instead of failing startup
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()

# Set Google Cloud credentials environment variable for the SDK
# The Google Cloud SDK reads GOOGLE_APPLICATION_CREDENTIALS from os.environ
if settings.google_application_credentials:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
