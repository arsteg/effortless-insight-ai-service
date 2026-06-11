"""
Schemas for extracted entities
"""

from typing import Optional, List
from datetime import date as DateType_
from pydantic import BaseModel, Field
from enum import Enum


class DateType(str, Enum):
    """Type of date extracted"""
    ISSUE_DATE = "issue_date"
    RESPONSE_DEADLINE = "response_deadline"
    PERIOD_FROM = "period_from"
    PERIOD_TO = "period_to"
    HEARING_DATE = "hearing_date"
    OTHER = "other"


class AmountType(str, Enum):
    """Type of amount extracted"""
    TAX = "tax"
    PENALTY = "penalty"
    INTEREST = "interest"
    TOTAL = "total"
    REFUND = "refund"
    OTHER = "other"


class GSTINInfo(BaseModel):
    """Extracted GSTIN information"""
    gstin: str = Field(..., description="15-character GSTIN")
    is_valid: bool = Field(..., description="Whether checksum is valid")
    state_code: str = Field(..., description="2-digit state code")
    state_name: Optional[str] = Field(None, description="State name")
    pan: str = Field(..., description="Extracted PAN from GSTIN")
    entity_type: str = Field(..., description="Entity type code")
    position_in_text: int = Field(..., description="Character position in text")
    confidence: float = Field(1.0, ge=0, le=1, description="Extraction confidence")


class DateInfo(BaseModel):
    """Extracted date information"""
    date: DateType_ = Field(..., description="Extracted date")
    date_type: DateType = Field(..., description="Type of date")
    original_text: str = Field(..., description="Original text that was parsed")
    position_in_text: int = Field(..., description="Character position in text")
    confidence: float = Field(1.0, ge=0, le=1, description="Extraction confidence")


class AmountInfo(BaseModel):
    """Extracted amount information"""
    amount: float = Field(..., description="Amount in INR")
    amount_type: AmountType = Field(..., description="Type of amount")
    original_text: str = Field(..., description="Original text that was parsed")
    position_in_text: int = Field(..., description="Character position in text")
    confidence: float = Field(1.0, ge=0, le=1, description="Extraction confidence")


class SectionReference(BaseModel):
    """Extracted section/rule reference"""
    reference: str = Field(..., description="Section or Rule reference (e.g., 'Section 73')")
    reference_type: str = Field(..., description="Type: section, rule, notification, circular")
    full_text: str = Field(..., description="Full reference text from document")
    position_in_text: int = Field(..., description="Character position in text")
    confidence: float = Field(1.0, ge=0, le=1, description="Extraction confidence")


class ExtractedEntities(BaseModel):
    """All entities extracted from a notice"""
    gstins: List[GSTINInfo] = Field(default_factory=list, description="All GSTINs found")
    dates: List[DateInfo] = Field(default_factory=list, description="All dates found")
    amounts: List[AmountInfo] = Field(default_factory=list, description="All amounts found")
    sections: List[SectionReference] = Field(default_factory=list, description="All section references")

    # Primary extracted values (best guess)
    primary_gstin: Optional[str] = Field(None, description="Most likely taxpayer GSTIN")
    issue_date: Optional[DateType_] = Field(None, description="Notice issue date")
    response_deadline: Optional[DateType_] = Field(None, description="Response deadline")
    period_from: Optional[DateType_] = Field(None, description="Tax period start")
    period_to: Optional[DateType_] = Field(None, description="Tax period end")
    tax_amount: Optional[float] = Field(None, description="Primary tax amount")
    penalty_amount: Optional[float] = Field(None, description="Penalty amount")
    interest_amount: Optional[float] = Field(None, description="Interest amount")
    total_amount: Optional[float] = Field(None, description="Total demand")

    # Notice identification
    notice_number: Optional[str] = Field(None, description="Notice reference number")
    arn: Optional[str] = Field(None, description="Application Reference Number")
    din: Optional[str] = Field(None, description="Document Identification Number")

    # Authority
    issuing_authority: Optional[str] = Field(None, description="Issuing officer/authority")
    jurisdiction: Optional[str] = Field(None, description="Tax jurisdiction")

    def get_primary_gstin_info(self) -> Optional[GSTINInfo]:
        """Get the primary GSTIN info if available"""
        if self.primary_gstin:
            for gstin_info in self.gstins:
                if gstin_info.gstin == self.primary_gstin:
                    return gstin_info
        return self.gstins[0] if self.gstins else None
