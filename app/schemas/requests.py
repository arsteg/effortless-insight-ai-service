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
    tone: Optional[str] = Field("formal", description="Tone of the response: formal, conciliatory, assertive")
    include_case_law: Optional[bool] = Field(True, alias="includeCaseLaw", description="Include relevant case law citations")

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
