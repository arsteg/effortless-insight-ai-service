"""
API request schemas
"""

from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class ProcessNoticeRequest(BaseModel):
    """Request model for notice processing - called by .NET API"""
    notice_id: UUID = Field(..., alias="noticeId", description="UUID of the notice to process")
    file_url: str = Field(..., alias="fileUrl", description="Presigned S3 URL for the notice file")
    organization_id: Optional[UUID] = Field(None, alias="organizationId", description="Organization ID for scoping")
    priority: Optional[str] = Field("normal", description="Processing priority: low, normal, high")
    callback_url: Optional[str] = Field(None, alias="callbackUrl", description="URL to call when processing completes")

    class Config:
        populate_by_name = True


class GenerateResponseRequest(BaseModel):
    """Request model for generating a draft response"""
    notice_id: UUID = Field(..., alias="noticeId", description="UUID of the notice")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for response generation")
    tone: Optional[str] = Field("formal", description="Tone of the response: formal, conciliatory, defensive")
    language: Optional[str] = Field("en", description="Language for the response: en (English) or hi (Hindi)")
    include_case_law: Optional[bool] = Field(True, alias="includeCaseLaw", description="Include relevant case law citations")
    points_to_address: Optional[list[str]] = Field(None, alias="pointsToAddress", description="Specific points to address in the response")
    additional_instructions: Optional[str] = Field(None, alias="additionalInstructions", description="Additional instructions for response generation")

    class Config:
        populate_by_name = True


class SimilarNoticesRequest(BaseModel):
    """Request model for finding similar notices"""
    notice_id: UUID = Field(..., alias="noticeId", description="UUID of the notice to find similar to")
    organization_id: Optional[UUID] = Field(None, alias="organizationId", description="Scope to organization's notices")
    limit: int = Field(5, ge=1, le=20, description="Number of similar notices to return")

    class Config:
        populate_by_name = True


class SearchRequest(BaseModel):
    """Request model for semantic search"""
    query: str = Field(..., min_length=3, description="Search query")
    source_type: Optional[str] = Field(None, alias="sourceType", description="Filter by source type")
    organization_id: Optional[UUID] = Field(None, alias="organizationId", description="Scope to organization")
    limit: int = Field(10, ge=1, le=50, description="Number of results to return")

    class Config:
        populate_by_name = True


class IndexKnowledgeRequest(BaseModel):
    """Request model for reindexing knowledge base"""
    source_type: Optional[str] = Field(None, alias="sourceType", description="Reindex only specific source type")
    force: bool = Field(False, description="Force reindex even if already indexed")

    class Config:
        populate_by_name = True


class ExtractAllegationsRequest(BaseModel):
    """Request model for extracting allegations from a notice"""
    notice_id: UUID = Field(..., alias="noticeId", description="UUID of the notice")
    notice_text: Optional[str] = Field(None, alias="noticeText", description="OCR text of the notice (optional, fetched from DB if not provided)")

    class Config:
        populate_by_name = True


class AllegationData(BaseModel):
    """Individual allegation data for response generation"""
    id: str = Field(..., description="Allegation ID (e.g., ALG-001)")
    serial_number: int = Field(..., alias="serialNumber", description="Serial number in notice")
    description: str = Field(..., description="Allegation description")
    category: str = Field(..., description="Category of allegation")
    legal_provision: Optional[str] = Field(None, alias="legalProvision", description="Section/Rule cited")
    amount_involved: Optional[float] = Field(None, alias="amountInvolved", description="Amount for this allegation")
    period: Optional[str] = Field(None, description="Tax period")
    evidence_cited: Optional[list[str]] = Field(None, alias="evidenceCited", description="Evidence cited by department")

    class Config:
        populate_by_name = True


class GenerateAllegationWiseDraftRequest(BaseModel):
    """Request model for generating allegation-wise draft responses"""
    notice_id: UUID = Field(..., alias="noticeId", description="UUID of the notice")
    notice_text: Optional[str] = Field(None, alias="noticeText", description="Full OCR transcript supplied by the authorized API")
    allegations: Optional[list[AllegationData]] = Field(None, description="Pre-extracted allegations (optional)")
    tone: Optional[str] = Field("formal", description="Tone: formal, conciliatory, defensive")
    language: Optional[str] = Field("en", description="Language: en or hi")
    allegation_overrides: Optional[Dict[str, str]] = Field(None, alias="allegationOverrides", description="Custom instructions per allegation ID")
    include_case_law: Optional[bool] = Field(True, alias="includeCaseLaw", description="Include case law references")
    taxpayer_context: Optional[Dict[str, Any]] = Field(None, alias="taxpayerContext", description="Additional taxpayer context")

    class Config:
        populate_by_name = True


class RegenerateAllegationResponseRequest(BaseModel):
    """Request model for regenerating a single allegation response"""
    notice_id: UUID = Field(..., alias="noticeId", description="UUID of the notice")
    allegation: AllegationData = Field(..., description="The allegation to respond to")
    tone: Optional[str] = Field("formal", description="Tone: formal, conciliatory, defensive")
    language: Optional[str] = Field("en", description="Language: en or hi")
    custom_instructions: Optional[str] = Field(None, alias="customInstructions", description="Specific instructions for this allegation")
    taxpayer_context: Optional[Dict[str, Any]] = Field(None, alias="taxpayerContext", description="Additional taxpayer context")

    class Config:
        populate_by_name = True
