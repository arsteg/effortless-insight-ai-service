"""
API response schemas - using camelCase for .NET compatibility
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date
from pydantic import BaseModel, Field, field_validator


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase"""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class CamelCaseModel(BaseModel):
    """Base model with camelCase serialization for .NET compatibility"""

    class Config:
        populate_by_name = True
        alias_generator = to_camel
        json_encoders = {
            UUID: str,
            date: lambda v: v.isoformat() if v else None,
        }


class ActionItem(CamelCaseModel):
    """Action item from AI analysis"""
    priority: int = Field(..., ge=1, le=10, description="Priority level 1-10")
    action: str = Field(..., description="Action title")
    description: str = Field(..., description="Detailed description")
    due_in_days: Optional[int] = Field(None, description="Days until due")
    assignee_suggestion: Optional[str] = Field(None, description="Suggested assignee type")

    @field_validator('priority', mode='before')
    @classmethod
    def parse_priority(cls, v):
        """Handle LLM returning priority as string"""
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 5  # Default to medium priority
        return v

    @field_validator('due_in_days', mode='before')
    @classmethod
    def parse_null_int(cls, v):
        """Handle LLM returning 'null' as string instead of JSON null"""
        if v is None or v == "null" or v == "":
            return None
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return None
        return v

    @field_validator('assignee_suggestion', mode='before')
    @classmethod
    def parse_null_string(cls, v):
        """Handle LLM returning 'null' as string instead of JSON null"""
        if v == "null" or v == "":
            return None
        return v


class RequiredDocument(CamelCaseModel):
    """Required document for notice response"""
    document: str = Field(..., description="Document name")
    mandatory: bool = Field(..., description="Whether the document is mandatory")

    @field_validator('mandatory', mode='before')
    @classmethod
    def parse_bool(cls, v):
        """Handle LLM returning boolean as string"""
        if isinstance(v, str):
            return v.lower() in ('true', 'yes', '1')
        return v


class LegalReference(CamelCaseModel):
    """Legal reference from GST Act/Rules"""
    section: str = Field(..., description="Section or Rule reference")
    description: str = Field(..., description="What the section means in context")


class NoticeMetadata(CamelCaseModel):
    """Extracted metadata from the notice"""
    notice_type: Optional[str] = Field(None, description="Type of notice (DRC-01, ASMT-10, etc.)")
    notice_category: Optional[str] = Field(None, description="Category (assessment, demand, etc.)")
    notice_number: Optional[str] = Field(None, description="Notice reference number")
    gstin: Optional[str] = Field(None, description="15-digit GSTIN")
    issue_date: Optional[date] = Field(None, description="Date notice was issued")
    response_deadline: Optional[date] = Field(None, description="Response due date")
    tax_amount: Optional[float] = Field(None, description="Tax amount in dispute")
    penalty_amount: Optional[float] = Field(None, description="Penalty amount")
    interest_amount: Optional[float] = Field(None, description="Interest amount")
    period_from: Optional[date] = Field(None, description="Start of tax period")
    period_to: Optional[date] = Field(None, description="End of tax period")
    issuing_authority: Optional[str] = Field(None, description="Issuing authority name")

    @field_validator('notice_type', 'notice_category', 'notice_number', 'gstin', 'issuing_authority', mode='before')
    @classmethod
    def parse_null_string(cls, v):
        """Handle LLM returning 'null' as string instead of JSON null"""
        if v == "null" or v == "":
            return None
        return v

    @field_validator('tax_amount', 'penalty_amount', 'interest_amount', mode='before')
    @classmethod
    def parse_null_float(cls, v):
        """Handle LLM returning 'null' as string instead of JSON null"""
        if v is None or v == "null" or v == "":
            return None
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return v

    @field_validator('issue_date', 'response_deadline', 'period_from', 'period_to', mode='before')
    @classmethod
    def parse_null_date(cls, v):
        """Handle LLM returning 'null' as string instead of JSON null"""
        if v is None or v == "null" or v == "":
            return None
        return v


class AiReportData(CamelCaseModel):
    """Complete AI analysis report"""
    risk_score: int = Field(..., ge=0, le=100, description="Risk score 0-100")
    risk_level: str = Field(..., description="Risk level: low, medium, high, critical")
    summary_en: str = Field(..., description="Executive summary in English")
    summary_hi: str = Field(..., description="Summary in Hindi")
    plain_english: str = Field(..., description="Plain English explanation")
    metadata: NoticeMetadata = Field(..., description="Extracted metadata")
    action_items: List[ActionItem] = Field(default_factory=list, description="Recommended actions")
    required_documents: List[RequiredDocument] = Field(default_factory=list, description="Required documents")
    legal_references: List[LegalReference] = Field(default_factory=list, description="Relevant legal references")
    confidence_scores: Dict[str, int] = Field(default_factory=dict, description="Confidence scores for each field")

    @field_validator('risk_score', mode='before')
    @classmethod
    def parse_risk_score(cls, v):
        """Handle LLM returning risk_score as string"""
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 50  # Default to medium risk
        return v


class AiProcessingResult(CamelCaseModel):
    """
    Main response model for notice processing - matches .NET IAiServiceClient interface

    This is the response returned to the .NET API after processing a notice.
    """
    success: bool = Field(..., description="Whether processing succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")
    report: Optional[AiReportData] = Field(None, description="AI analysis report")


class SimilarNotice(CamelCaseModel):
    """Similar notice from vector search"""
    notice_id: UUID = Field(..., description="UUID of the similar notice")
    similarity_score: float = Field(..., ge=0, le=1, description="Similarity score 0-1")
    notice_type: Optional[str] = Field(None, description="Type of the similar notice")
    summary: Optional[str] = Field(None, description="Summary of the similar notice")


class SimilarNoticesResponse(CamelCaseModel):
    """Response for similar notices endpoint"""
    success: bool = Field(True)
    notice_id: UUID = Field(..., description="Original notice ID")
    similar_notices: List[SimilarNotice] = Field(default_factory=list)


class GenerateResponseResponse(CamelCaseModel):
    """Response for generate response endpoint"""
    success: bool = Field(True)
    draft: str = Field(..., description="Generated draft response")


class SearchResult(CamelCaseModel):
    """Search result from semantic search"""
    source_type: str = Field(..., description="Type of source")
    source_id: UUID = Field(..., description="ID of the source")
    content: str = Field(..., description="Content snippet")
    score: float = Field(..., description="Relevance score")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(CamelCaseModel):
    """Response for semantic search endpoint"""
    success: bool = Field(True)
    query: str = Field(..., description="Original query")
    results: List[SearchResult] = Field(default_factory=list)
    total: int = Field(0, description="Total number of results")


class HealthCheck(CamelCaseModel):
    """Individual health check result"""
    status: str = Field(..., description="ok, degraded, or error")
    latency_ms: Optional[int] = Field(None, description="Latency in milliseconds")
    message: Optional[str] = Field(None, description="Additional message")


class HealthResponse(CamelCaseModel):
    """Health check response"""
    status: str = Field("healthy", description="Overall health status")
    service: str = Field("ai-service", description="Service name")
    version: str = Field("1.0.0", description="Service version")


class ReadinessResponse(CamelCaseModel):
    """Readiness check response"""
    status: str = Field(..., description="ready or not_ready")
    checks: Dict[str, HealthCheck] = Field(default_factory=dict)
