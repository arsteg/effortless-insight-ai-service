"""
Unit tests for Pydantic schemas
"""

import pytest
from datetime import date
from uuid import uuid4

from app.schemas.requests import (
    ProcessNoticeRequest,
    GenerateResponseRequest,
    SimilarNoticesRequest,
    SearchRequest,
)
from app.schemas.responses import (
    AiProcessingResult,
    AiReportData,
    NoticeMetadata,
    ActionItem,
    RequiredDocument,
    LegalReference,
    HealthResponse,
)
from app.schemas.entities import (
    GSTINInfo,
    DateInfo,
    DateType,
    AmountInfo,
    AmountType,
    SectionReference,
    ExtractedEntities,
)
from app.schemas.internal import (
    PipelineContext,
    AnalysisOutput,
    OCROutput,
    ClassificationOutput,
)
from app.schemas.report import (
    ConfidenceScores,
    RiskAssessment,
)


class TestProcessNoticeRequest:
    """Test cases for ProcessNoticeRequest"""

    def test_valid_request(self):
        """Test valid request creation"""
        request = ProcessNoticeRequest(
            notice_id=uuid4(),
            file_url="https://example.com/file.pdf",
        )
        assert request.notice_id is not None
        assert request.file_url == "https://example.com/file.pdf"

    def test_optional_fields(self):
        """Test optional fields have defaults"""
        request = ProcessNoticeRequest(
            notice_id=uuid4(),
            file_url="https://example.com/file.pdf",
        )
        assert request.organization_id is None
        assert request.priority == "normal"

    def test_with_organization(self):
        """Test request with organization"""
        org_id = uuid4()
        request = ProcessNoticeRequest(
            notice_id=uuid4(),
            file_url="https://example.com/file.pdf",
            organization_id=org_id,
        )
        assert request.organization_id == org_id


class TestGenerateResponseRequest:
    """Test cases for GenerateResponseRequest"""

    def test_valid_request(self):
        """Test valid request"""
        request = GenerateResponseRequest(
            notice_id=uuid4(),
        )
        assert request.notice_id is not None

    def test_with_context(self):
        """Test request with additional context"""
        request = GenerateResponseRequest(
            notice_id=uuid4(),
            context={"key": "value"},
        )
        assert request.context == {"key": "value"}


class TestSimilarNoticesRequest:
    """Test cases for SimilarNoticesRequest"""

    def test_valid_request(self):
        """Test valid request"""
        request = SimilarNoticesRequest(
            notice_id=uuid4(),
        )
        assert request.notice_id is not None

    def test_default_limit(self):
        """Test default limit"""
        request = SimilarNoticesRequest(notice_id=uuid4())
        assert request.limit == 5


class TestSearchRequest:
    """Test cases for SearchRequest"""

    def test_valid_request(self):
        """Test valid request"""
        request = SearchRequest(
            query="section 73 penalty",
        )
        assert request.query == "section 73 penalty"


class TestAiProcessingResult:
    """Test cases for AiProcessingResult"""

    def test_success_result(self):
        """Test successful result"""
        result = AiProcessingResult(
            success=True,
            report=AiReportData(
                risk_score=65,
                risk_level="high",
                summary_en="Test summary",
                summary_hi="परीक्षण",
                plain_english="Simple explanation",
                metadata=NoticeMetadata(),
                action_items=[],
                required_documents=[],
                legal_references=[],
                confidence_scores={},
            )
        )
        assert result.success is True
        assert result.error is None

    def test_failure_result(self):
        """Test failure result"""
        result = AiProcessingResult(
            success=False,
            error="Processing failed",
        )
        assert result.success is False
        assert result.error == "Processing failed"


class TestActionItem:
    """Test cases for ActionItem"""

    def test_valid_action_item(self):
        """Test valid action item"""
        item = ActionItem(
            priority=1,
            action="Submit reply",
            description="Prepare and submit reply to notice",
            due_in_days=30,
        )
        assert item.priority == 1
        assert item.action == "Submit reply"


class TestRequiredDocument:
    """Test cases for RequiredDocument"""

    def test_mandatory_document(self):
        """Test mandatory document"""
        doc = RequiredDocument(
            document="GSTR-3B Returns",
            mandatory=True,
        )
        assert doc.document == "GSTR-3B Returns"
        assert doc.mandatory is True


class TestLegalReference:
    """Test cases for LegalReference"""

    def test_valid_reference(self):
        """Test valid legal reference"""
        ref = LegalReference(
            section="Section 73",
            description="Recovery without fraud",
        )
        assert ref.section == "Section 73"


class TestHealthResponse:
    """Test cases for HealthResponse"""

    def test_healthy_response(self):
        """Test healthy response"""
        response = HealthResponse(
            status="healthy",
            service="ai-service",
            version="1.0.0",
        )
        assert response.status == "healthy"


class TestGSTINInfo:
    """Test cases for GSTINInfo"""

    def test_valid_gstin_info(self):
        """Test valid GSTIN info"""
        info = GSTINInfo(
            gstin="29AADCB2230M1ZV",
            is_valid=True,
            state_code="29",
            state_name="Karnataka",
            pan="AADCB2230M",
            entity_type="Company",
            position_in_text=100,
            confidence=0.95,
        )
        assert info.gstin == "29AADCB2230M1ZV"
        assert info.is_valid is True


class TestDateInfo:
    """Test cases for DateInfo"""

    def test_valid_date_info(self):
        """Test valid date info"""
        info = DateInfo(
            date=date(2024, 1, 15),
            date_type=DateType.ISSUE_DATE,
            original_text="15/01/2024",
            position_in_text=50,
            confidence=0.95,
        )
        assert info.date == date(2024, 1, 15)
        assert info.date_type == DateType.ISSUE_DATE


class TestAmountInfo:
    """Test cases for AmountInfo"""

    def test_valid_amount_info(self):
        """Test valid amount info"""
        info = AmountInfo(
            amount=500000.0,
            amount_type=AmountType.TAX,
            original_text="Rs. 5,00,000/-",
            position_in_text=200,
            confidence=0.90,
        )
        assert info.amount == 500000.0
        assert info.amount_type == AmountType.TAX


class TestSectionReference:
    """Test cases for SectionReference"""

    def test_valid_section_reference(self):
        """Test valid section reference"""
        ref = SectionReference(
            reference="Section 73",
            reference_type="section",
            full_text="Section 73 of CGST Act",
            position_in_text=300,
            confidence=0.90,
        )
        assert ref.reference == "Section 73"


class TestExtractedEntities:
    """Test cases for ExtractedEntities"""

    def test_empty_entities(self):
        """Test empty extracted entities"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
        )
        assert len(entities.gstins) == 0


class TestOCROutput:
    """Test cases for OCROutput"""

    def test_valid_ocr_output(self):
        """Test valid OCR output"""
        output = OCROutput(
            success=True,
            text="Extracted text content",
            confidence=0.95,
            provider="google_document_ai",
            page_count=3,
        )
        assert output.success is True
        assert output.confidence == 0.95


class TestClassificationOutput:
    """Test cases for ClassificationOutput"""

    def test_valid_classification_output(self):
        """Test valid classification output"""
        output = ClassificationOutput(
            success=True,
            notice_type="DRC-01",
            notice_category="demand",
            confidence=0.90,
        )
        assert output.success is True
        assert output.notice_type == "DRC-01"


class TestPipelineContext:
    """Test cases for PipelineContext"""

    def test_valid_context(self):
        """Test valid pipeline context"""
        context = PipelineContext(
            notice_id=uuid4(),
            file_url="https://example.com/file.pdf",
        )
        assert context.notice_id is not None


class TestAnalysisOutput:
    """Test cases for AnalysisOutput"""

    def test_valid_output(self):
        """Test valid analysis output"""
        output = AnalysisOutput(
            success=True,
            risk_score=65,
            risk_level="high",
            summary_en="English summary",
            summary_hi="Hindi summary",
            plain_english="Plain explanation",
        )
        assert output.success is True
        assert output.risk_score == 65


class TestConfidenceScores:
    """Test cases for ConfidenceScores"""

    def test_valid_scores(self):
        """Test valid confidence scores"""
        scores = ConfidenceScores(
            notice_type=85,
            deadline=90,
            amount=80,
            gstin=95,
            risk_assessment=75,
            overall=85,
        )
        assert scores.overall == 85

    def test_to_dict(self):
        """Test to_dict method"""
        scores = ConfidenceScores(
            notice_type=85,
            deadline=90,
            amount=80,
            gstin=95,
            risk_assessment=75,
            overall=85,
        )
        result = scores.to_dict()
        assert "noticeType" in result
        assert result["overall"] == 85


class TestRiskAssessment:
    """Test cases for RiskAssessment"""

    def test_valid_assessment(self):
        """Test valid risk assessment"""
        assessment = RiskAssessment(
            score=75,
            level="high",
            notice_category_score=80,
            tax_amount_score=70,
            deadline_urgency_score=85,
        )
        assert assessment.score == 75
        assert assessment.level == "high"

    def test_weights_default(self):
        """Test weights have default values"""
        assessment = RiskAssessment(score=75, level="high")
        assert "notice_category" in assessment.weights
        assert assessment.weights["notice_category"] == 0.25
