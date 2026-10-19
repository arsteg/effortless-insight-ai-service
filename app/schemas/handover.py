"""
Handover summary schema for case transfers.
"""

from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class HandoverSummary(BaseModel):
    """AI-generated summary for case transfers."""

    background: str = Field(
        ...,
        description="Case context and key issues - brief overview of the notice and situation"
    )
    work_completed: List[str] = Field(
        default_factory=list,
        description="Actions already taken on this case"
    )
    pending_items: List[str] = Field(
        default_factory=list,
        description="Outstanding tasks that need attention"
    )
    next_steps: List[str] = Field(
        default_factory=list,
        description="Recommended immediate actions for the new handler"
    )
    key_deadlines: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Critical dates with descriptions, e.g., [{'date': '2024-01-15', 'description': 'Response deadline'}]"
    )
    key_contacts: List[str] = Field(
        default_factory=list,
        description="Important contacts related to the case"
    )
    risk_summary: Optional[str] = Field(
        None,
        description="Brief risk assessment summary"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this summary was generated"
    )


class HandoverRequest(BaseModel):
    """Request to generate a handover summary."""
    notice_id: str = Field(..., description="ID of the notice")
    notice_summary: Optional[str] = Field(None, description="AI summary of the notice")
    notice_type: Optional[str] = Field(None, description="Type of notice")
    notice_category: Optional[str] = Field(None, description="Category of notice")
    risk_level: Optional[str] = Field(None, description="Risk level")
    response_deadline: Optional[str] = Field(None, description="Response deadline")
    activity_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of activities: [{'action': '...', 'user': '...', 'date': '...'}]"
    )
    current_status: Optional[str] = Field(None, description="Current status of the notice")
    assigned_to: Optional[str] = Field(None, description="Currently assigned user")
    additional_context: Optional[str] = Field(None, description="Any additional context")


class HandoverResponse(BaseModel):
    """Response containing the generated handover summary."""
    success: bool = Field(...)
    summary: Optional[HandoverSummary] = Field(None)
    error: Optional[str] = Field(None)
    processing_time_ms: int = Field(0)
