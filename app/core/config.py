"""
Application configuration using Pydantic Settings
"""

from typing import Optional, List
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
    openai_api_key: str = ""
    openai_model: str = "gpt-4-turbo-preview"
    openai_embedding_model: str = "text-embedding-3-large"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096

    # Google Cloud (Primary OCR)
    google_cloud_project_id: str = ""
    google_cloud_location: str = "us"
    google_document_ai_processor_id: str = ""

    # Azure Form Recognizer (Fallback OCR)
    azure_form_recognizer_endpoint: str = ""
    azure_form_recognizer_key: str = ""

    # OCR Settings
    ocr_confidence_threshold: float = 0.70

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

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
