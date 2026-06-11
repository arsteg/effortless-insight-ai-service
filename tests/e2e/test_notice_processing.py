"""
End-to-end tests for notice processing API
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


class TestNoticeProcessingAPI:
    """E2E tests for notice processing endpoints"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_api_health_endpoint(self, client):
        """Test API health endpoint"""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_process_notice_validation(self, client):
        """Test notice processing request validation"""
        # Missing required fields
        response = client.post("/api/v1/process/notice", json={})

        assert response.status_code == 422  # Validation error

    def test_process_notice_with_mock(self, client):
        """Test notice processing with mocked services"""
        from app.schemas.responses import AiProcessingResult, AiReportData, NoticeMetadata

        mock_result = AiProcessingResult(
            success=True,
            report=AiReportData(
                risk_score=65,
                risk_level="high",
                summary_en="Test summary",
                summary_hi="परीक्षण सारांश",
                plain_english="Simple explanation",
                metadata=NoticeMetadata(),
                action_items=[],
                required_documents=[],
                legal_references=[],
                confidence_scores={},
            )
        )

        with patch('app.api.endpoints.process.PipelineOrchestrator') as MockOrchestrator:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(return_value=mock_result)
            MockOrchestrator.return_value = mock_instance

            response = client.post("/api/v1/process/notice", json={
                "noticeId": str(uuid4()),
                "fileUrl": "https://example.com/test.pdf",
            })

            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True

    def test_generate_response_validation(self, client):
        """Test response generation validation"""
        response = client.post("/api/v1/process/generate-response", json={})

        assert response.status_code == 422

    def test_find_similar_validation(self, client):
        """Test similar notices validation"""
        response = client.post("/api/v1/process/similar", json={})

        assert response.status_code == 422

    def test_embeddings_search_validation(self, client):
        """Test embeddings search validation"""
        response = client.post("/api/v1/embeddings/search", json={
            "query": ""  # Empty query
        })

        # Should fail validation for empty query
        assert response.status_code == 422

    def test_admin_status_endpoint(self, client):
        """Test admin status endpoint"""
        with patch('app.api.endpoints.admin.OCRService') as MockOCR, \
             patch('app.api.endpoints.admin.LLMClient') as MockLLM:

            mock_ocr = MagicMock()
            mock_ocr.get_provider_status = AsyncMock(return_value={"status": "available"})
            MockOCR.return_value = mock_ocr

            mock_llm = MagicMock()
            mock_llm.is_available = AsyncMock(return_value=True)
            mock_llm.model = "gpt-4-turbo"
            MockLLM.return_value = mock_llm

            response = client.get("/api/v1/admin/status")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
