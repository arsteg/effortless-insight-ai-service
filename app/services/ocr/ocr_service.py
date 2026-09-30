"""
OCR Service with fallback strategy
"""

import asyncio
from io import BytesIO
from pypdf import PdfReader, PdfWriter
import time
import hashlib
from typing import Optional, Tuple
import structlog
import httpx

from app.core.config import settings
from app.services.ocr.base import OCRResult
from app.services.ocr.google_document_ai import GoogleDocumentAI
from app.services.ocr.azure_form_recognizer import AzureFormRecognizer

logger = structlog.get_logger()

# Confidence threshold for fallback
OCR_CONFIDENCE_THRESHOLD = getattr(settings, 'ocr_confidence_threshold', 0.70)


class OCRService:
    """
    OCR Service with fallback strategy

    Primary: Google Document AI
    Fallback: Azure Form Recognizer (if confidence < threshold or primary fails)
    """

    def __init__(self):
        self.google_ai = GoogleDocumentAI()
        self.azure_fr = AzureFormRecognizer()
        self.confidence_threshold = OCR_CONFIDENCE_THRESHOLD

    async def extract_text(self, file_url: str) -> OCRResult:
        content, mime_type = await self._download_document(file_url)
        if content is None:
            return OCRResult(success=False, error=f"Failed to download document: {mime_type}")
        return await self.extract_from_bytes(content, mime_type)

    @staticmethod
    def _pdf_batches(content: bytes):
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("PDF is password protected; upload an unlocked copy")
        count = len(reader.pages)
        if not count:
            raise ValueError("PDF contains no pages")
        # Keep each online OCR request within the standard 15-page limit.
        batches = []
        for start in range(0, count, 15):
            writer = PdfWriter()
            for page in reader.pages[start:start + 15]:
                writer.add_page(page)
            output = BytesIO()
            writer.write(output)
            batches.append((start, min(15, count - start), output.getvalue()))
        return batches

    async def extract_from_bytes(self, content: bytes, mime_type: str) -> OCRResult:
        started = time.monotonic()
        mime_type = mime_type.split(";")[0].strip().lower()
        if not content:
            return OCRResult(success=False, error="Uploaded document is empty")
        if mime_type != "application/pdf":
            return await self._extract_batch(content, mime_type)
        try:
            batches = await asyncio.to_thread(self._pdf_batches, content)
        except Exception as exc:
            return OCRResult(success=False, error=f"Cannot read PDF: {exc}")

        results = []
        tables = []
        for offset, count, batch in batches:
            logger.info("OCR batch started", first_page=offset + 1, last_page=offset + count)
            result = await self._extract_batch(batch, mime_type, expected_pages=count)
            if not result.success:
                return OCRResult(
                    success=False,
                    error=f"OCR failed for pages {offset + 1}-{offset + count}: {result.error}",
                    processing_time_ms=int((time.monotonic() - started) * 1000),
                )
            results.append(result)
            tables.extend({**table, "page": table.get("page", 1) + offset} for table in result.tables)
        page_count = sum(result.page_count for result in results)
        return OCRResult(
            success=True,
            text="\n\n".join(result.text for result in results),
            confidence=sum(result.confidence * result.page_count for result in results) / page_count,
            provider="+".join(dict.fromkeys(result.provider for result in results)),
            page_count=page_count,
            tables=tables,
            page_texts=[text for result in results for text in result.page_texts],
            page_confidences=[value for result in results for value in result.page_confidences],
            processing_time_ms=int((time.monotonic() - started) * 1000),
        )

    async def _extract_batch(self, content: bytes, mime_type: str, expected_pages=None) -> OCRResult:
        errors = []
        candidates = []
        for provider in (self.google_ai, self.azure_fr):
            try:
                if not await provider.is_available():
                    errors.append(f"{provider.name}: not configured")
                    continue
                result = await provider.process_document(content, mime_type)
                if result.success and expected_pages is not None and result.page_count != expected_pages:
                    errors.append(f"{provider.name}: returned {result.page_count} of {expected_pages} pages")
                    continue
                if result.success and not result.text.strip():
                    errors.append(f"{provider.name}: no readable text found")
                    continue
                if result.success:
                    candidates.append(result)
                    if result.confidence >= self.confidence_threshold:
                        return max(candidates, key=lambda item: item.confidence)
                else:
                    errors.append(f"{provider.name}: {result.error or 'unknown error'}")
            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
        if candidates:
            return max(candidates, key=lambda item: item.confidence)
        error = "; ".join(errors)
        logger.error("All OCR providers failed", error=error)
        return OCRResult(success=False, error=error)

    async def _download_document(self, url: str) -> Tuple[Optional[bytes], str]:
        """
        Download document from URL

        Returns:
            Tuple of (content bytes, mime_type or error message)
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                content = response.content
                content_type = response.headers.get('content-type', 'application/pdf')

                # Clean up content type
                mime_type = content_type.split(';')[0].strip()

                return content, mime_type

        except httpx.TimeoutException:
            return None, "Download timeout"
        except httpx.HTTPStatusError as e:
            return None, f"HTTP error: {e.response.status_code}"
        except Exception as e:
            return None, str(e)

    def get_content_hash(self, content: bytes) -> str:
        """Get SHA-256 hash of content for deduplication"""
        return hashlib.sha256(content).hexdigest()

    async def get_provider_status(self) -> dict:
        """Get status of OCR providers"""
        return {
            "google_document_ai": {
                "available": await self.google_ai.is_available(),
                "name": self.google_ai.name,
            },
            "azure_form_recognizer": {
                "available": await self.azure_fr.is_available(),
                "name": self.azure_fr.name,
            },
            "confidence_threshold": self.confidence_threshold,
        }
