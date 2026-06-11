"""
Custom exceptions for the AI service
"""


class AIServiceException(Exception):
    """Base exception for AI service"""

    def __init__(self, message: str, code: str = "AI_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class OCRError(AIServiceException):
    """OCR processing error"""

    def __init__(self, message: str, provider: str = None):
        self.provider = provider
        super().__init__(message, "OCR_ERROR")


class LLMError(AIServiceException):
    """LLM processing error"""

    def __init__(self, message: str, model: str = None):
        self.model = model
        super().__init__(message, "LLM_ERROR")


class ValidationError(AIServiceException):
    """Validation error"""

    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR")


class PipelineError(AIServiceException):
    """Pipeline processing error"""

    def __init__(self, message: str, stage: str = None):
        self.stage = stage
        super().__init__(message, "PIPELINE_ERROR")


class RateLimitError(AIServiceException):
    """Rate limit exceeded"""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMIT")


class ConfigurationError(AIServiceException):
    """Configuration error"""

    def __init__(self, message: str, setting: str = None):
        self.setting = setting
        super().__init__(message, "CONFIG_ERROR")


class ExternalServiceError(AIServiceException):
    """External service error"""

    def __init__(self, message: str, service: str = None):
        self.service = service
        super().__init__(message, "EXTERNAL_SERVICE_ERROR")
