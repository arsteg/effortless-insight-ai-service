"""
Processing job model for tracking notice processing status
"""

from enum import Enum
from sqlalchemy import Column, String, Text, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin, UUIDMixin


class ProcessingStatus(str, Enum):
    """Status of a processing job"""
    PENDING = "pending"
    PREPROCESSING = "preprocessing"
    OCR = "ocr"
    ENTITY_EXTRACTION = "entity_extraction"
    CLASSIFICATION = "classification"
    RAG_RETRIEVAL = "rag_retrieval"
    LLM_ANALYSIS = "llm_analysis"
    VERIFICATION = "verification"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJob(Base, UUIDMixin, TimestampMixin):
    """
    Processing job model for tracking notice processing through the pipeline

    Tracks the status, timing, and results of each processing stage.
    """
    __tablename__ = "processing_jobs"

    # Notice reference
    notice_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    organization_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Status tracking
    status = Column(String(50), default=ProcessingStatus.PENDING.value, nullable=False, index=True)
    current_stage = Column(String(50), nullable=True)

    # Stage timings (in milliseconds)
    preprocessing_time_ms = Column(Integer, nullable=True)
    ocr_time_ms = Column(Integer, nullable=True)
    entity_extraction_time_ms = Column(Integer, nullable=True)
    classification_time_ms = Column(Integer, nullable=True)
    rag_retrieval_time_ms = Column(Integer, nullable=True)
    llm_analysis_time_ms = Column(Integer, nullable=True)
    verification_time_ms = Column(Integer, nullable=True)
    report_generation_time_ms = Column(Integer, nullable=True)
    total_time_ms = Column(Integer, nullable=True)

    # OCR details
    ocr_provider = Column(String(50), nullable=True)  # google_document_ai, azure_form_recognizer
    ocr_confidence = Column(Float, nullable=True)
    ocr_page_count = Column(Integer, nullable=True)
    ocr_text_length = Column(Integer, nullable=True)

    # LLM details
    llm_model = Column(String(100), nullable=True)
    llm_input_tokens = Column(Integer, nullable=True)
    llm_output_tokens = Column(Integer, nullable=True)
    llm_total_cost = Column(Float, nullable=True)

    # Result
    result = Column(JSONB, nullable=True)

    # Error tracking
    error = Column(Text, nullable=True)
    error_stage = Column(String(50), nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    # Input data
    file_url = Column(Text, nullable=True)
    file_type = Column(String(50), nullable=True)  # pdf, image, etc.

    # Extracted raw text
    raw_text = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ProcessingJob(id={self.id}, notice_id={self.notice_id}, status={self.status})>"

    def mark_stage_complete(self, stage: str, duration_ms: int) -> None:
        """Mark a processing stage as complete with its duration"""
        timing_field = f"{stage}_time_ms"
        if hasattr(self, timing_field):
            setattr(self, timing_field, duration_ms)

    def fail(self, error: str, stage: str) -> None:
        """Mark the job as failed"""
        self.status = ProcessingStatus.FAILED.value
        self.error = error
        self.error_stage = stage
        self.retry_count += 1
