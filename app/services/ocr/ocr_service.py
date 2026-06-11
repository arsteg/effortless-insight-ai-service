"""
OCR Service with fallback strategy
"""

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
        """
        Extract text from a document URL

        Args:
            file_url: URL of the document (presigned S3 URL)

        Returns:
            OCRResult with extracted text
        """
        start_time = time.time()

        logger.info("Starting OCR extraction", file_url=file_url[:80] + "...")

        try:
            # Download the document
            content, mime_type = await self._download_document(file_url)
            if content is None:
                return OCRResult(
                    success=False,
                    error=f"Failed to download document: {mime_type}",
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )

            logger.info(
                "Document downloaded",
                size=len(content),
                mime_type=mime_type
            )

            # Try Google Document AI first
            if await self.google_ai.is_available():
                result = await self.google_ai.process_document(content, mime_type)

                if result.success and result.confidence >= self.confidence_threshold:
                    logger.info(
                        "OCR completed with Google Document AI",
                        confidence=result.confidence,
                        page_count=result.page_count
                    )
                    return result

                # Low confidence or failure - try Azure fallback
                logger.warning(
                    "Google Document AI result below threshold, trying Azure fallback",
                    confidence=result.confidence,
                    threshold=self.confidence_threshold,
                    error=result.error
                )

            # Try Azure Form Recognizer as fallback
            if await self.azure_fr.is_available():
                azure_result = await self.azure_fr.process_document(content, mime_type)

                if azure_result.success:
                    # If we had a Google result, compare and use the better one
                    if 'result' in locals() and result.success:
                        if azure_result.confidence > result.confidence:
                            logger.info(
                                "Using Azure result (higher confidence)",
                                azure_confidence=azure_result.confidence,
                                google_confidence=result.confidence
                            )
                            return azure_result
                        else:
                            logger.info(
                                "Using Google result (higher confidence despite being below threshold)",
                                azure_confidence=azure_result.confidence,
                                google_confidence=result.confidence
                            )
                            return result
                    else:
                        logger.info(
                            "OCR completed with Azure Form Recognizer",
                            confidence=azure_result.confidence,
                            page_count=azure_result.page_count
                        )
                        return azure_result

                logger.error("Azure Form Recognizer also failed", error=azure_result.error)

            # Return whatever result we have (even if below threshold)
            if 'result' in locals() and result.success:
                logger.warning(
                    "Returning low-confidence Google result (no fallback available)",
                    confidence=result.confidence
                )
                return result

            # Both providers failed or unavailable
            return OCRResult(
                success=False,
                error="All OCR providers failed or unavailable",
                processing_time_ms=int((time.time() - start_time) * 1000)
            )

        except Exception as e:
            logger.error("OCR extraction failed", error=str(e))
            return OCRResult(
                success=False,
                error=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000)
            )

    async def extract_from_bytes(self, content: bytes, mime_type: str) -> OCRResult:
        """
        Extract text from document bytes directly

        Args:
            content: Document content as bytes
            mime_type: MIME type of the document

        Returns:
            OCRResult with extracted text
        """
        start_time = time.time()

        # Try Google Document AI first
        if await self.google_ai.is_available():
            result = await self.google_ai.process_document(content, mime_type)

            if result.success and result.confidence >= self.confidence_threshold:
                return result

        # Try Azure fallback
        if await self.azure_fr.is_available():
            azure_result = await self.azure_fr.process_document(content, mime_type)
            if azure_result.success:
                return azure_result

        # Return Google result even if below threshold
        if 'result' in locals() and result.success:
            return result

        return OCRResult(
            success=False,
            error="All OCR providers failed",
            processing_time_ms=int((time.time() - start_time) * 1000)
        )

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
