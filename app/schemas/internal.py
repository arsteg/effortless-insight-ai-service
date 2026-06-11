"""
Internal DTOs for pipeline processing
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.entities import ExtractedEntities
from app.schemas.report import AIReport, VerificationResult


class OCROutput(BaseModel):
    """Output from OCR processing stage"""
    success: bool = Field(...)
    text: str = Field("")
    confidence: float = Field(0.0, ge=0, le=1)
    provider: str = Field("")  # google_document_ai, azure_form_recognizer
    page_count: int = Field(0)
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = Field(None)

    # Per-page details
    page_confidences: List[float] = Field(default_factory=list)
    page_texts: List[str] = Field(default_factory=list)


class EntityExtractionOutput(BaseModel):
    """Output from entity extraction stage"""
    success: bool = Field(...)
    entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    error: Optional[str] = Field(None)
    processing_time_ms: int = Field(0)


class ClassificationOutput(BaseModel):
    """Output from classification stage"""
    success: bool = Field(...)
    notice_type: Optional[str] = Field(None)  # DRC-01, ASMT-10, etc.
    notice_category: Optional[str] = Field(None)  # assessment, demand, registration, etc.
    sub_category: Optional[str] = Field(None)
    confidence: float = Field(0.0, ge=0, le=1)
    error: Optional[str] = Field(None)

    # All classifications with scores
    all_classifications: List[Dict[str, Any]] = Field(default_factory=list)


class RAGContext(BaseModel):
    """Context retrieved from RAG"""
    success: bool = Field(...)
    contexts: List[Dict[str, Any]] = Field(default_factory=list)
    total_retrieved: int = Field(0)
    error: Optional[str] = Field(None)

    # Individual context entries
    gst_rules: List[str] = Field(default_factory=list)
    circulars: List[str] = Field(default_factory=list)
    case_laws: List[str] = Field(default_factory=list)
    templates: List[str] = Field(default_factory=list)


class AnalysisOutput(BaseModel):
    """Output from LLM analysis stage"""
    success: bool = Field(...)
    risk_score: int = Field(50, ge=0, le=100)
    risk_level: str = Field("medium")
    summary_en: str = Field("")
    summary_hi: str = Field("")
    plain_english: str = Field("")
    action_items: List[Dict[str, Any]] = Field(default_factory=list)
    required_documents: List[Dict[str, Any]] = Field(default_factory=list)
    legal_references: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_scores: Dict[str, int] = Field(default_factory=dict)
    error: Optional[str] = Field(None)

    # Token usage
    input_tokens: int = Field(0)
    output_tokens: int = Field(0)


class VerificationOutput(BaseModel):
    """Output from verification stage"""
    success: bool = Field(...)
    verification: VerificationResult = Field(default_factory=VerificationResult)
    adjustments_made: List[str] = Field(default_factory=list)
    error: Optional[str] = Field(None)


class PipelineContext(BaseModel):
    """Context passed through the processing pipeline"""
    # Request info
    notice_id: UUID
    organization_id: Optional[UUID] = Field(None)
    file_url: str
    priority: str = Field("normal")

    # Timing
    start_time: datetime = Field(default_factory=datetime.utcnow)
    stage_timings: Dict[str, int] = Field(default_factory=dict)

    # Stage outputs
    ocr_output: Optional[OCROutput] = Field(None)
    entity_output: Optional[EntityExtractionOutput] = Field(None)
    classification_output: Optional[ClassificationOutput] = Field(None)
    rag_context: Optional[RAGContext] = Field(None)
    analysis_output: Optional[AnalysisOutput] = Field(None)
    verification_output: Optional[VerificationOutput] = Field(None)

    # Final report
    report: Optional[AIReport] = Field(None)

    # Error tracking
    current_stage: str = Field("preprocessing")
    error: Optional[str] = Field(None)
    failed: bool = Field(False)

    # Raw data
    raw_text: str = Field("")
    file_type: str = Field("")
    file_size: int = Field(0)

    def record_stage_time(self, stage: str, duration_ms: int) -> None:
        """Record timing for a pipeline stage"""
        self.stage_timings[stage] = duration_ms

    def get_total_time_ms(self) -> int:
        """Get total processing time in milliseconds"""
        return sum(self.stage_timings.values())

    def mark_failed(self, stage: str, error: str) -> None:
        """Mark the pipeline as failed"""
        self.current_stage = stage
        self.error = error
        self.failed = True

    class Config:
        arbitrary_types_allowed = True
