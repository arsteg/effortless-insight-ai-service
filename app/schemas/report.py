"""
Schemas for AI analysis report
"""

from typing import Optional, List, Dict, Any
from datetime import date
from pydantic import BaseModel, Field

from app.schemas.responses import ActionItem, RequiredDocument, LegalReference, NoticeMetadata


class ConfidenceScores(BaseModel):
    """Confidence scores for different aspects of the analysis"""
    notice_type: int = Field(0, ge=0, le=100, description="Confidence in notice type classification")
    deadline: int = Field(0, ge=0, le=100, description="Confidence in deadline extraction")
    amount: int = Field(0, ge=0, le=100, description="Confidence in amount extraction")
    gstin: int = Field(0, ge=0, le=100, description="Confidence in GSTIN extraction")
    risk_assessment: int = Field(0, ge=0, le=100, description="Confidence in risk assessment")
    overall: int = Field(0, ge=0, le=100, description="Overall confidence score")

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary for JSON serialization"""
        return {
            "noticeType": self.notice_type,
            "deadline": self.deadline,
            "amount": self.amount,
            "gstin": self.gstin,
            "riskAssessment": self.risk_assessment,
            "overall": self.overall,
        }


class RiskAssessment(BaseModel):
    """Risk assessment breakdown"""
    score: int = Field(..., ge=0, le=100, description="Overall risk score")
    level: str = Field(..., description="Risk level: low, medium, high, critical")

    # Component scores (each 0-100)
    notice_category_score: int = Field(0, ge=0, le=100, description="Risk from notice category")
    tax_amount_score: int = Field(0, ge=0, le=100, description="Risk from tax amount")
    deadline_urgency_score: int = Field(0, ge=0, le=100, description="Risk from deadline urgency")
    penalty_potential_score: int = Field(0, ge=0, le=100, description="Risk from penalty potential")
    prior_history_score: int = Field(0, ge=0, le=100, description="Risk from prior history")
    complexity_score: int = Field(0, ge=0, le=100, description="Risk from notice complexity")

    # Weights used
    weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "notice_category": 0.25,
            "tax_amount": 0.20,
            "deadline_urgency": 0.20,
            "penalty_potential": 0.15,
            "prior_history": 0.10,
            "complexity": 0.10,
        }
    )

    @staticmethod
    def score_to_level(score: int) -> str:
        """Convert score to risk level"""
        if score < 25:
            return "low"
        elif score < 50:
            return "medium"
        elif score < 75:
            return "high"
        else:
            return "critical"


class VerificationResult(BaseModel):
    """Result of fact-checking and verification"""
    is_verified: bool = Field(..., description="Whether all facts were verified")
    issues: List[str] = Field(default_factory=list, description="List of issues found")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")

    # Specific verifications
    deadline_verified: bool = Field(True, description="Deadline found in original text")
    amounts_verified: bool = Field(True, description="Amounts match extracted values")
    sections_valid: bool = Field(True, description="Section references are valid")
    gstin_valid: bool = Field(True, description="GSTIN passes checksum")
    dates_consistent: bool = Field(True, description="Dates are logically consistent")

    # Hallucination detection
    potential_hallucinations: List[str] = Field(
        default_factory=list,
        description="Fields that may contain hallucinated information"
    )


class AIReport(BaseModel):
    """Complete AI analysis report"""
    # Risk assessment
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: str = Field(...)
    risk_assessment: Optional[RiskAssessment] = Field(None)

    # Summaries
    summary_en: str = Field(..., description="Executive summary in English")
    summary_hi: str = Field(..., description="Summary in Hindi")
    plain_english: str = Field(..., description="Plain English explanation")

    # Metadata
    metadata: NoticeMetadata = Field(...)

    # Action items
    action_items: List[ActionItem] = Field(default_factory=list)

    # Required documents
    required_documents: List[RequiredDocument] = Field(default_factory=list)

    # Legal references
    legal_references: List[LegalReference] = Field(default_factory=list)

    # Confidence
    confidence_scores: ConfidenceScores = Field(default_factory=ConfidenceScores)

    # Verification
    verification: Optional[VerificationResult] = Field(None)

    # Processing metadata
    processing_time_ms: Optional[int] = Field(None)
    model_used: Optional[str] = Field(None)
    ocr_confidence: Optional[float] = Field(None)

    def to_ai_report_data(self):
        """Convert to AiReportData for API response"""
        from app.schemas.responses import AiReportData

        return AiReportData(
            risk_score=self.risk_score,
            risk_level=self.risk_level,
            summary_en=self.summary_en,
            summary_hi=self.summary_hi,
            plain_english=self.plain_english,
            metadata=self.metadata,
            action_items=self.action_items,
            required_documents=self.required_documents,
            legal_references=self.legal_references,
            confidence_scores=self.confidence_scores.to_dict(),
        )
