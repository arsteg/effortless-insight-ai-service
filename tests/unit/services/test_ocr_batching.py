import unittest
from io import BytesIO
from unittest.mock import AsyncMock
from pypdf import PdfReader, PdfWriter
from app.services.ocr.ocr_service import OCRService
from app.services.ocr.base import OCRResult


def pdf(pages, password=None):
    writer = PdfWriter()
    for i in range(pages):
        writer.add_blank_page(width=100 + i, height=100)
    if password:
        writer.encrypt(password)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


class OCRBatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = OCRService()
        self.service.google_ai = AsyncMock()
        self.service.google_ai.name = 'google'
        self.service.google_ai.is_available.return_value = True
        self.service.azure_fr = AsyncMock()
        self.service.azure_fr.name = 'azure'
        self.service.azure_fr.is_available.return_value = False

    async def test_page_boundaries_and_order(self):
        for count in (1, 15, 16, 25, 31):
            with self.subTest(pages=count):
                async def process(content, mime):
                    pages = PdfReader(BytesIO(content)).pages
                    texts = [str(int(page.mediabox.width) - 100) for page in pages]
                    return OCRResult(success=True, text=' '.join(texts), confidence=.9,
                                     provider='google', page_count=len(pages), page_texts=texts,
                                     tables=[{'page': len(pages)}])
                self.service.google_ai.process_document.side_effect = process
                result = await self.service.extract_from_bytes(pdf(count), 'application/pdf')
                self.assertTrue(result.success, result.error)
                self.assertEqual(result.page_count, count)
                self.assertEqual(result.page_texts, list(map(str, range(count))))
                self.assertEqual(result.tables[-1]['page'], count)

    async def test_failure_is_not_partial_success(self):
        self.service.google_ai.process_document.side_effect = [
            OCRResult(success=True, text='first', confidence=.9, page_count=15),
            OCRResult(success=False, error='quota exceeded')]
        result = await self.service.extract_from_bytes(pdf(25), 'application/pdf')
        self.assertFalse(result.success)
        self.assertIn('pages 16-25', result.error)
        self.assertIn('quota exceeded', result.error)
        self.assertIn('azure: not configured', result.error)
        self.assertEqual(result.text, '')

    async def test_incomplete_provider_result_uses_fallback(self):
        self.service.google_ai.process_document.return_value = OCRResult(success=True, text='partial', page_count=1)
        self.service.azure_fr.is_available.return_value = True
        self.service.azure_fr.process_document.return_value = OCRResult(success=True, text='all', page_count=2, confidence=.8)
        result = await self.service.extract_from_bytes(pdf(2), 'application/pdf')
        self.assertTrue(result.success)
        self.assertEqual(result.text, 'all')

    async def test_images_pass_through_and_exceptions_fall_back(self):
        self.service.google_ai.process_document.side_effect = RuntimeError('offline')
        self.service.azure_fr.is_available.return_value = True
        self.service.azure_fr.process_document.return_value = OCRResult(success=True, text='image text', page_count=1, confidence=.8)
        for mime in ('image/png', 'image/jpeg', 'image/tiff'):
            result = await self.service.extract_from_bytes(b'image', mime)
            self.assertTrue(result.success)
            self.service.azure_fr.process_document.assert_awaited_with(b'image', mime)

    async def test_invalid_and_encrypted_files(self):
        for content in (b'', b'broken', pdf(0), pdf(1, 'secret')):
            result = await self.service.extract_from_bytes(content, 'application/pdf')
            self.assertFalse(result.success)
        self.service.google_ai.process_document.assert_not_awaited()

    async def test_url_upload_uses_same_batching(self):
        self.service._download_document = AsyncMock(return_value=(pdf(25), 'application/pdf'))
        self.service._extract_batch = AsyncMock(side_effect=[
            OCRResult(success=True, text='a', page_count=15, confidence=.9),
            OCRResult(success=True, text='b', page_count=10, confidence=.6)])
        result = await self.service.extract_text('https://example.test/document')
        self.assertEqual(result.page_count, 25)
        self.assertAlmostEqual(result.confidence, .78)


class VisionCoverageTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_vision_cannot_replace_full_ocr(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from app.services.pipeline.orchestrator import PipelineOrchestrator
        pipeline = PipelineOrchestrator.__new__(PipelineOrchestrator)
        pipeline.vision_extractor = SimpleNamespace(extract=AsyncMock(return_value=SimpleNamespace(
            success=True, transcript='partial vision ' * 100, pages_processed=10)))
        context = SimpleNamespace(notice_id='test', _document_content=b'pdf',
                                  raw_text='complete OCR', ocr_output=SimpleNamespace(page_count=25),
                                  record_stage_time=Mock())
        await pipeline._stage_vision_extraction(context)
        self.assertEqual(context.raw_text, 'complete OCR')
        self.assertTrue(context.vision_output.success)


if __name__ == '__main__':
    unittest.main()
