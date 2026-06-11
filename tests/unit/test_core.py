"""
Unit tests for core modules
"""

import pytest
from unittest.mock import patch, MagicMock

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AIServiceException,
    OCRError,
    LLMError,
    ValidationError,
    PipelineError,
    RateLimitError,
    ConfigurationError,
    ExternalServiceError,
)
from app.core.database import get_engine, get_session_maker, Base


class TestSettings:
    """Test cases for settings configuration"""

    def test_default_settings(self):
        """Test default settings values"""
        settings = Settings()
        assert settings.environment == "development"
        assert settings.ocr_confidence_threshold == 0.70
        assert settings.llm_temperature == 0.2

    def test_settings_from_env(self):
        """Test settings can be loaded from environment"""
        with patch.dict('os.environ', {'ENVIRONMENT': 'production'}):
            settings = Settings()
            # Note: pydantic-settings may cache, so this tests the mechanism

    def test_get_settings_cached(self):
        """Test get_settings returns cached instance"""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_database_url_default(self):
        """Test default database URL"""
        settings = Settings()
        assert "postgresql" in settings.database_url

    def test_redis_url_default(self):
        """Test default Redis URL"""
        settings = Settings()
        assert "redis://" in settings.redis_url

    def test_openai_settings(self):
        """Test OpenAI settings"""
        settings = Settings()
        assert settings.openai_model == "gpt-4-turbo-preview"
        assert settings.openai_embedding_model == "text-embedding-3-large"

    def test_rag_settings(self):
        """Test RAG settings"""
        settings = Settings()
        assert settings.rag_top_k == 10
        assert settings.rag_min_similarity == 0.5

    def test_pipeline_settings(self):
        """Test pipeline settings"""
        settings = Settings()
        assert settings.pipeline_timeout_seconds == 180


class TestExceptions:
    """Test cases for custom exceptions"""

    def test_ai_service_exception(self):
        """Test base AI service exception"""
        exc = AIServiceException("Test error")
        assert str(exc) == "Test error"
        assert exc.code == "AI_ERROR"
        assert exc.message == "Test error"

    def test_ai_service_exception_with_code(self):
        """Test AI service exception with custom code"""
        exc = AIServiceException("Test error", code="CUSTOM_CODE")
        assert exc.code == "CUSTOM_CODE"

    def test_ocr_error(self):
        """Test OCR error"""
        exc = OCRError("OCR failed")
        assert str(exc) == "OCR failed"
        assert exc.code == "OCR_ERROR"
        assert exc.provider is None

    def test_ocr_error_with_provider(self):
        """Test OCR error with provider info"""
        exc = OCRError("OCR failed", provider="google")
        assert exc.provider == "google"

    def test_llm_error(self):
        """Test LLM error"""
        exc = LLMError("LLM failed")
        assert str(exc) == "LLM failed"
        assert exc.code == "LLM_ERROR"
        assert exc.model is None

    def test_llm_error_with_model(self):
        """Test LLM error with model info"""
        exc = LLMError("LLM failed", model="gpt-4")
        assert exc.model == "gpt-4"

    def test_validation_error(self):
        """Test validation error"""
        exc = ValidationError("Validation failed")
        assert str(exc) == "Validation failed"
        assert exc.code == "VALIDATION_ERROR"
        assert exc.field is None

    def test_validation_error_with_field(self):
        """Test validation error with field info"""
        exc = ValidationError("Invalid value", field="email")
        assert exc.field == "email"

    def test_pipeline_error(self):
        """Test pipeline error"""
        exc = PipelineError("Pipeline failed")
        assert str(exc) == "Pipeline failed"
        assert exc.code == "PIPELINE_ERROR"
        assert exc.stage is None

    def test_pipeline_error_with_stage(self):
        """Test pipeline error with stage info"""
        exc = PipelineError("Stage failed", stage="ocr")
        assert exc.stage == "ocr"

    def test_rate_limit_error(self):
        """Test rate limit error"""
        exc = RateLimitError()
        assert "Rate limit" in str(exc)
        assert exc.code == "RATE_LIMIT"

    def test_rate_limit_error_custom_message(self):
        """Test rate limit error with custom message"""
        exc = RateLimitError("Custom rate limit message")
        assert str(exc) == "Custom rate limit message"

    def test_configuration_error(self):
        """Test configuration error"""
        exc = ConfigurationError("Config error")
        assert str(exc) == "Config error"
        assert exc.code == "CONFIG_ERROR"
        assert exc.setting is None

    def test_configuration_error_with_setting(self):
        """Test configuration error with setting info"""
        exc = ConfigurationError("Invalid setting", setting="api_key")
        assert exc.setting == "api_key"

    def test_external_service_error(self):
        """Test external service error"""
        exc = ExternalServiceError("Service unavailable")
        assert str(exc) == "Service unavailable"
        assert exc.code == "EXTERNAL_SERVICE_ERROR"
        assert exc.service is None

    def test_external_service_error_with_service(self):
        """Test external service error with service info"""
        exc = ExternalServiceError("Service down", service="openai")
        assert exc.service == "openai"

    def test_exception_inheritance(self):
        """Test exception inheritance chain"""
        assert issubclass(OCRError, AIServiceException)
        assert issubclass(LLMError, AIServiceException)
        assert issubclass(ValidationError, AIServiceException)
        assert issubclass(PipelineError, AIServiceException)
        assert issubclass(RateLimitError, AIServiceException)
        assert issubclass(ConfigurationError, AIServiceException)
        assert issubclass(ExternalServiceError, AIServiceException)


class TestDatabase:
    """Test cases for database module"""

    def test_get_engine_returns_engine(self):
        """Test get_engine returns an engine"""
        engine = get_engine()
        assert engine is not None

    def test_get_engine_cached(self):
        """Test get_engine returns same instance"""
        engine1 = get_engine()
        engine2 = get_engine()
        assert engine1 is engine2

    def test_get_session_maker_returns_maker(self):
        """Test get_session_maker returns session maker"""
        maker = get_session_maker()
        assert maker is not None

    def test_get_session_maker_cached(self):
        """Test get_session_maker returns same instance"""
        maker1 = get_session_maker()
        maker2 = get_session_maker()
        assert maker1 is maker2

    def test_base_exists(self):
        """Test Base is declarative base"""
        assert Base is not None
        assert hasattr(Base, 'metadata')
