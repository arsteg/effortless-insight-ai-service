"""
Integration tests for the processing pipeline
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.ocr.base import OCRResult
from app.schemas.internal import AnalysisOutput


# Skip tests if OpenAI API key is not set
requires_openai = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY environment variable not set"
)


@requires_openai
class TestPipelineOrchestrator:
    """Integration tests for pipeline orchestrator"""

    @pytest.fixture
    def orchestrator(self):
        from app.services.pipeline.orchestrator import PipelineOrchestrator
        return PipelineOrchestrator()

    @pytest.fixture
    def mock_ocr_result(self):
        return OCRResult(
            success=True,
            text="""
            DRC-01 Show Cause Notice
            GSTIN: 29AADCB2230M1ZV
            Date: 15/01/2024
            Deadline: 14/02/2024
            Amount: Rs. 5,00,000/-
            Section 73 of CGST Act
            """,
            confidence=0.95,
            provider="google_document_ai",
            page_count=1,
        )

    @pytest.fixture
    def mock_analysis_result(self):
        return AnalysisOutput(
            success=True,
            risk_score=65,
            risk_level="high",
            summary_en="This is a DRC-01 show cause notice under Section 73.",
            summary_hi="यह धारा 73 के तहत DRC-01 कारण बताओ नोटिस है।",
            plain_english="You have received a notice asking you to explain discrepancies.",
            action_items=[
                {
                    "priority": 1,
                    "action": "Review documents",
                    "description": "Review all related documents",
                    "due_in_days": 15,
                }
            ],
            required_documents=[
                {"document": "GSTR-3B returns", "mandatory": True}
            ],
            legal_references=[
                {"section": "Section 73", "description": "Recovery without fraud"}
            ],
            confidence_scores={
                "notice_type": 90,
                "deadline": 85,
                "amount": 80,
                "overall": 85,
            },
            input_tokens=1000,
            output_tokens=500,
        )

    @pytest.mark.asyncio
    async def test_pipeline_success(
        self,
        orchestrator,
        mock_ocr_result,
        mock_analysis_result
    ):
        """Test successful pipeline execution"""
        notice_id = uuid4()
        file_url = "https://example.com/test.pdf"

        # Mock all external services
        with patch.object(orchestrator.preprocessor, 'process') as mock_preprocess, \
             patch.object(orchestrator.ocr_service, 'extract_text') as mock_ocr, \
             patch.object(orchestrator.classifier, 'classify') as mock_classify, \
             patch.object(orchestrator.rag_retriever, 'retrieve_for_notice') as mock_rag, \
             patch.object(orchestrator.analyzer, 'analyze') as mock_analyze:

            # Setup mocks
            mock_preprocess.return_value = MagicMock(
                failed=False,
                _document_content=b"test",
                _mime_type="application/pdf"
            )
            mock_ocr.return_value = mock_ocr_result
            mock_classify.return_value = MagicMock(
                success=True,
                notice_type="DRC-01",
                notice_category="demand"
            )
            mock_rag.return_value = MagicMock(success=True, gst_rules=[], circulars=[])
            mock_analyze.return_value = mock_analysis_result

            # Run pipeline
            result = await orchestrator.process(
                notice_id=notice_id,
                file_url=file_url,
            )

            assert result.success
            assert result.report is not None
            assert result.report.risk_score >= 0

    @pytest.mark.asyncio
    async def test_pipeline_ocr_failure(self, orchestrator):
        """Test pipeline handling of OCR failure"""
        notice_id = uuid4()
        file_url = "https://example.com/test.pdf"

        with patch.object(orchestrator.preprocessor, 'process') as mock_preprocess, \
             patch.object(orchestrator.ocr_service, 'extract_text') as mock_ocr:

            mock_preprocess.return_value = MagicMock(
                failed=False,
                _document_content=b"test",
                _mime_type="application/pdf"
            )
            mock_ocr.return_value = OCRResult(
                success=False,
                error="OCR service unavailable"
            )

            result = await orchestrator.process(
                notice_id=notice_id,
                file_url=file_url,
            )

            assert not result.success
            assert "OCR" in result.error or "ocr" in result.error

    @pytest.mark.asyncio
    async def test_pipeline_handles_exceptions(self, orchestrator):
        """Test pipeline handling of exceptions"""
        notice_id = uuid4()
        file_url = "https://example.com/test.pdf"

        with patch.object(orchestrator.preprocessor, 'process') as mock_preprocess:
            mock_preprocess.side_effect = Exception("Unexpected error")

            result = await orchestrator.process(
                notice_id=notice_id,
                file_url=file_url,
            )

            assert not result.success
            assert result.error is not None
