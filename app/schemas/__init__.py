"""
Pydantic schemas for API requests and responses
"""

from app.schemas.requests import (
    ProcessNoticeRequest,
    GenerateResponseRequest,
    SimilarNoticesRequest,
    SearchRequest,
    IndexKnowledgeRequest,
)
from app.schemas.responses import (
    AiProcessingResult,
    AiReportData,
    NoticeMetadata,
    ActionItem,
    RequiredDocument,
    LegalReference,
    SimilarNotice,
    GenerateResponseResponse,
    SimilarNoticesResponse,
    SearchResponse,
    SearchResult,
    HealthResponse,
    ReadinessResponse,
)
from app.schemas.entities import (
    ExtractedEntities,
    GSTINInfo,
    DateInfo,
    AmountInfo,
    SectionReference,
)
from app.schemas.report import (
    AIReport,
    RiskAssessment,
    ConfidenceScores,
)
from app.schemas.internal import (
    PipelineContext,
    OCROutput,
    EntityExtractionOutput,
    ClassificationOutput,
    RAGContext,
    AnalysisOutput,
    VerificationOutput,
)

__all__ = [
    # Requests
    "ProcessNoticeRequest",
    "GenerateResponseRequest",
    "SimilarNoticesRequest",
    "SearchRequest",
    "IndexKnowledgeRequest",
    # Responses
    "AiProcessingResult",
    "AiReportData",
    "NoticeMetadata",
    "ActionItem",
    "RequiredDocument",
    "LegalReference",
    "SimilarNotice",
    "GenerateResponseResponse",
    "SimilarNoticesResponse",
    "SearchResponse",
    "SearchResult",
    "HealthResponse",
    "ReadinessResponse",
    # Entities
    "ExtractedEntities",
    "GSTINInfo",
    "DateInfo",
    "AmountInfo",
    "SectionReference",
    # Report
    "AIReport",
    "RiskAssessment",
    "ConfidenceScores",
    # Internal
    "PipelineContext",
    "OCROutput",
    "EntityExtractionOutput",
    "ClassificationOutput",
    "RAGContext",
    "AnalysisOutput",
    "VerificationOutput",
]
