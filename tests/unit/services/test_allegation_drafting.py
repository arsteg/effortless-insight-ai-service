import json
import unittest
from unittest.mock import AsyncMock
from app.services.extraction.allegation_extractor import AllegationExtractor
from app.schemas.allegations import Allegation


class AllegationDraftTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = AsyncMock()
        self.service = AllegationExtractor(self.client)
        self.allegations = [Allegation(id=f"ALG-{i}", serial_number=i, description=f"Issue {i}", category="Other") for i in (1, 2)]

    def answer(self, data):
        self.client.complete.return_value = {"content": json.dumps(data), "input_tokens": 10, "output_tokens": 20, "model": "test"}

    async def test_regeneration_formats_prompt_and_calls_model(self):
        self.answer({"response_text": "Revised reply"})
        result = await self.service.regenerate_single_response(self.allegations[0])
        self.assertEqual(result.response_text, "Revised reply")
        self.client.complete.assert_awaited_once()

    async def test_failed_regeneration_raises_instead_of_replacing_reply(self):
        self.client.complete.side_effect = RuntimeError("unavailable")
        with self.assertRaises(ValueError):
            await self.service.regenerate_single_response(self.allegations[0])

    async def test_blank_regeneration_is_failure(self):
        self.answer({"response_text": " "})
        with self.assertRaises(ValueError):
            await self.service.regenerate_single_response(self.allegations[0])

    async def test_missing_duplicate_unknown_or_blank_responses_fail(self):
        for responses in ([], [{"allegation_id": "ALG-1", "response_text": "One"}],
                          [{"allegation_id": "ALG-1", "response_text": "One"}] * 2,
                          [{"allegation_id": "UNKNOWN", "response_text": "One"}, {"allegation_id": "ALG-2", "response_text": "Two"}],
                          [{"allegation_id": "ALG-1", "response_text": ""}, {"allegation_id": "ALG-2", "response_text": "Two"}]):
            with self.subTest(responses=responses):
                self.answer({"responses": responses})
                result = await self.service.generate_allegation_responses(self.allegations, "notice")
                self.assertFalse(result.success)

    async def test_complete_response_set_succeeds_and_evidence_defaults_unavailable(self):
        self.answer({"responses": [{"allegation_id": a.id, "response_text": "Reply", "supporting_evidence": [{"document_name": "Challan"}]} for a in self.allegations]})
        result = await self.service.generate_allegation_responses(self.allegations, "notice")
        self.assertTrue(result.success)
        self.assertEqual(len(result.responses), 2)
        self.assertFalse(result.responses[0].supporting_evidence[0].available)

    async def test_extraction_preserves_two_allegations_and_amounts(self):
        self.answer({"allegations": [{"id": "ALG-1", "description": "Unpaid tax", "amount_involved": "2,00,000"}, {"id": "ALG-2", "description": "Wrong ITC", "amount_involved": 50000}]})
        result = await self.service.extract_allegations("Two allegations in notice")
        self.assertTrue(result.success)
        self.assertEqual(result.total_amount, 250000)

    async def test_invalid_extraction_does_not_silently_drop_an_allegation(self):
        self.answer({"allegations": [{"id": "ALG-1", "description": "Valid"}, {"id": "ALG-2", "description": None}]})
        result = await self.service.extract_allegations("notice")
        self.assertFalse(result.success)

    async def test_supplied_transcript_avoids_notice_text_database_lookup(self):
        from unittest.mock import patch
        from uuid import uuid4
        from app.api.endpoints.process import generate_allegation_wise_draft
        from app.schemas.requests import GenerateAllegationWiseDraftRequest
        from app.schemas.allegations import AllegationExtractionResult, AllegationWiseDraftResponse
        extractor = AsyncMock()
        extractor.extract_allegations.return_value = AllegationExtractionResult(allegations=self.allegations)
        extractor.generate_allegation_responses.return_value = AllegationWiseDraftResponse(allegations=self.allegations)
        request = GenerateAllegationWiseDraftRequest(noticeId=uuid4(), noticeText="Full notice transcript")
        with patch("app.api.endpoints.process.AllegationExtractor", return_value=extractor), \
             patch("app.api.endpoints.process._fetch_notice_text", new_callable=AsyncMock) as fetch_text, \
             patch("app.api.endpoints.process._fetch_notice_details", new_callable=AsyncMock, return_value=None):
            result = await generate_allegation_wise_draft(request, AsyncMock())
        self.assertTrue(result.success)
        fetch_text.assert_not_awaited()
        extractor.extract_allegations.assert_awaited_once_with("Full notice transcript")
