"""
Allegation-related schemas for point-wise reply drafting
"""

from typing import Optional, List
from decimal import Decimal
from pydantic import Field, field_validator, model_validator

from app.schemas.responses import CamelCaseModel, AI_DISCLAIMER, GenerateResponseMetadata


class SupportingDocument(CamelCaseModel):
    """Supporting document reference for an allegation response"""
    document_name: str = Field(..., description="Name of the supporting document")
    document_type: str = Field(..., description="Type of document (invoice, return, bank statement, etc.)")
    relevance: str = Field(..., description="How this document supports the response")
    available: bool = Field(False, description="Whether the document is already available")


class CaseLawReference(CamelCaseModel):
    """Case law citation for legal support"""
    citation: str = Field(..., description="Case citation (e.g., '2023 (1) TMI 123 - CESTAT')")
    court: str = Field(..., description="Court name (Supreme Court, High Court, CESTAT, etc.)")
    principle: str = Field(..., description="Legal principle or ruling that applies")
    relevance: str = Field(..., description="How this case law supports the response")


class Allegation(CamelCaseModel):
    """
    Individual allegation extracted from a GST notice.

    Each allegation represents a distinct issue or charge raised by the tax authority.
    """
    id: str = Field(..., description="Unique identifier (e.g., 'ALG-001')")
    serial_number: int = Field(..., description="Sequential number of the allegation in the notice")
    description: str = Field(..., description="Full text of the allegation")
    category: str = Field(..., description="Category of allegation (e.g., 'Tax Evasion', 'ITC Mismatch', 'Non-filing')")
    legal_provision: Optional[str] = Field(None, description="Section/Rule cited (e.g., 'Section 74(1)', 'Rule 36(4)')")
    amount_involved: Optional[float] = Field(None, description="Tax/penalty amount for this specific allegation")
    period: Optional[str] = Field(None, description="Tax period covered (e.g., 'FY 2022-23', 'Apr-Jun 2023')")
    evidence_cited: List[str] = Field(default_factory=list, description="Documents/evidence cited by the department")
    page_reference: Optional[str] = Field(None, description="Page/paragraph reference in the notice")

    @field_validator('amount_involved', mode='before')
    @classmethod
    def parse_amount(cls, v):
        """Handle various numeric formats from LLM"""
        if v is None or v == "null" or v == "":
            return None
        if isinstance(v, str):
            # Remove currency symbols and commas
            cleaned = v.replace('₹', '').replace(',', '').replace('Rs.', '').replace('Rs', '').strip()
            try:
                return float(cleaned)
            except ValueError:
                return None
        if isinstance(v, Decimal):
            return float(v)
        return v

    @field_validator('serial_number', mode='before')
    @classmethod
    def parse_serial(cls, v):
        """Handle serial number as string"""
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 1
        return v


class AllegationResponse(CamelCaseModel):
    """
    AI-generated response for a single allegation.

    Contains the draft response text along with supporting legal basis,
    evidence, and identification of any missing information.
    """
    allegation_id: str = Field(..., description="Links to Allegation.id")
    response_text: str = Field(..., description="Draft reply text for this allegation")
    legal_basis: List[str] = Field(default_factory=list, description="Legal provisions supporting the response")
    supporting_evidence: List[SupportingDocument] = Field(default_factory=list, description="Documents supporting the response")
    missing_information: List[str] = Field(default_factory=list, description="Information/documents still needed")
    case_law_references: List[CaseLawReference] = Field(default_factory=list, description="Relevant case law citations")
    confidence: float = Field(0.7, ge=0.0, le=1.0, description="Confidence score for this response")
    status: str = Field("needs_review", description="Status: 'complete', 'needs_review', or 'missing_info'")

    @model_validator(mode='after')
    def reconcile_evidence_status(self):
        for document in self.supporting_evidence:
            if not document.available and document.document_name not in self.missing_information:
                self.missing_information.append(document.document_name)
        if self.missing_information:
            self.status = "missing_info"
        return self

    @field_validator('confidence', mode='before')
    @classmethod
    def parse_confidence(cls, v):
        """Handle confidence as string or percentage"""
        if v is None or v == "null":
            return 0.5
        if isinstance(v, str):
            cleaned = v.replace('%', '').strip()
            try:
                val = float(cleaned)
                # If it's a percentage (> 1), convert to decimal
                return val / 100 if val > 1 else val
            except ValueError:
                return 0.5
        return v

    @field_validator('status', mode='before')
    @classmethod
    def normalize_status(cls, v):
        """Normalize status values"""
        if v is None or v == "null":
            return "needs_review"
        status_map = {
            "complete": "complete",
            "completed": "complete",
            "done": "complete",
            "needs_review": "needs_review",
            "review": "needs_review",
            "pending": "needs_review",
            "missing_info": "missing_info",
            "incomplete": "missing_info",
            "missing": "missing_info",
        }
        return status_map.get(v.lower(), "needs_review") if isinstance(v, str) else "needs_review"


class AllegationExtractionResult(CamelCaseModel):
    """Result of extracting allegations from a notice"""
    success: bool = Field(True)
    error: Optional[str] = Field(None, description="Error message if extraction failed")
    allegations: List[Allegation] = Field(default_factory=list, description="List of extracted allegations")
    total_amount: Optional[float] = Field(None, description="Sum of all allegation amounts")
    metadata: Optional[GenerateResponseMetadata] = Field(None, description="Processing metadata")


class AllegationWiseDraftRequest(CamelCaseModel):
    """Request for generating allegation-wise draft responses"""
    notice_id: str = Field(..., description="UUID of the notice")
    tone: str = Field("formal", description="Response tone: formal, conciliatory, defensive")
    language: str = Field("en", description="Response language: en, hi")
    allegation_overrides: Optional[dict] = Field(None, description="Custom instructions per allegation ID")
    include_case_law: bool = Field(True, description="Whether to include case law references")
    taxpayer_context: Optional[dict] = Field(None, description="Additional context about the taxpayer's situation")


class AllegationWiseDraftResponse(CamelCaseModel):
    """Complete response for allegation-wise draft generation"""
    success: bool = Field(True)
    error: Optional[str] = Field(None, description="Error message if generation failed")
    allegations: List[Allegation] = Field(default_factory=list, description="Extracted allegations")
    responses: List[AllegationResponse] = Field(default_factory=list, description="Generated responses per allegation")
    combined_draft: Optional[str] = Field(None, description="Full combined document for download")
    missing_info_summary: List[str] = Field(default_factory=list, description="Aggregated list of missing information")
    disclaimer: str = Field(default=AI_DISCLAIMER, description="Fixed AI-usage disclaimer")
    metadata: Optional[GenerateResponseMetadata] = Field(None, description="Processing metadata")
