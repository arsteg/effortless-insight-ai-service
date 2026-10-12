"""Self-contained inspection regression tests; no model or mailbox calls."""
import base64
import importlib.util
import io
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfWriter

spec = importlib.util.spec_from_file_location("email_notice_endpoint", Path(__file__).parents[2] / "app/api/endpoints/email_notices.py")
endpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(endpoint)


class EmailNoticeInspectionTests(unittest.IsolatedAsyncioTestCase):
    def test_rejects_invalid_document(self):
        with self.assertRaises(ValueError):
            endpoint.extract_pdf_text(base64.b64encode(b"not a pdf").decode())

    def test_blank_pdf_returns_no_text_without_model(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        stream = io.BytesIO()
        writer.write(stream)
        self.assertEqual("", endpoint.extract_pdf_text(base64.b64encode(stream.getvalue()).decode()))

    def test_snippet_size_is_enforced(self):
        with self.assertRaises(ValidationError):
            endpoint.ClassificationRequest(snippet="x" * 6001, subject="notice", sender="n@gst.gov.in", organizationId=uuid4())

    async def test_classification_has_bounded_output_and_single_attempt(self):
        client = AsyncMock()
        client.complete.return_value = {"content": '{"isNotice":true,"confidence":0.92}'}
        request = endpoint.ClassificationRequest(snippet="A GST notice excerpt", subject="Notice", sender="n@gst.gov.in", organizationId=uuid4())
        with patch.object(endpoint, "LLMClient", return_value=client):
            result = await endpoint.classify(request)
        self.assertTrue(result.isNotice)
        kwargs = client.complete.call_args.kwargs
        self.assertEqual(150, kwargs["max_tokens"])
        self.assertEqual(1, kwargs["retry_count"])
        self.assertFalse(kwargs["use_cache"])

    async def test_invalid_model_response_is_not_accepted(self):
        client = AsyncMock()
        client.complete.return_value = {"content": '{"isNotice":true,"confidence":5}'}
        request = endpoint.ClassificationRequest(snippet="Notice", subject="", sender="n@gst.gov.in", organizationId=uuid4())
        with patch.object(endpoint, "LLMClient", return_value=client), self.assertRaises(HTTPException) as error:
            await endpoint.classify(request)
        self.assertEqual(503, error.exception.status_code)


if __name__ == "__main__":
    unittest.main()
