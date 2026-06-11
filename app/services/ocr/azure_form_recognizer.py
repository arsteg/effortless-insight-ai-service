"""
Azure Form Recognizer OCR provider (fallback)
"""

import time
from typing import Optional, List, Dict, Any
import structlog

from app.core.config import settings
from app.services.ocr.base import OCRProvider, OCRResult

logger = structlog.get_logger()


class AzureFormRecognizer(OCRProvider):
    """Azure Form Recognizer OCR provider - used as fallback"""

    def __init__(self):
        self.endpoint = getattr(settings, 'azure_form_recognizer_endpoint', '')
        self.api_key = getattr(settings, 'azure_form_recognizer_key', '')
        self._client = None

    @property
    def name(self) -> str:
        return "azure_form_recognizer"

    async def is_available(self) -> bool:
        """Check if Azure Form Recognizer is configured"""
        return bool(self.endpoint and self.api_key)

    async def _get_client(self):
        """Get or create the Form Recognizer client"""
        if self._client is None:
            try:
                from azure.ai.formrecognizer.aio import DocumentAnalysisClient
                from azure.core.credentials import AzureKeyCredential

                self._client = DocumentAnalysisClient(
                    endpoint=self.endpoint,
                    credential=AzureKeyCredential(self.api_key)
                )
            except ImportError:
                logger.warning("Azure Form Recognizer SDK not installed")
                return None
        return self._client

    async def process_document(self, content: bytes, mime_type: str) -> OCRResult:
        """
        Process document using Azure Form Recognizer

        Args:
            content: Document content as bytes
            mime_type: MIME type

        Returns:
            OCRResult with extracted text
        """
        start_time = time.time()

        if not await self.is_available():
            return OCRResult(
                success=False,
                provider=self.name,
                error="Azure Form Recognizer is not configured"
            )

        try:
            client = await self._get_client()
            if client is None:
                return OCRResult(
                    success=False,
                    provider=self.name,
                    error="Azure SDK not available"
                )

            logger.info(
                "Processing document with Azure Form Recognizer",
                mime_type=mime_type,
                content_size=len(content)
            )

            # Use prebuilt-read model for general document OCR
            poller = await client.begin_analyze_document(
                "prebuilt-read",
                document=content
            )
            result = await poller.result()

            # Extract text from all pages
            full_text_parts = []
            page_texts = []
            page_confidences = []

            for page in result.pages:
                page_text_parts = []

                # Extract lines
                for line in page.lines:
                    page_text_parts.append(line.content)

                page_text = "\n".join(page_text_parts)
                page_texts.append(page_text)
                full_text_parts.append(page_text)

                # Calculate page confidence from words
                if page.words:
                    word_confidences = [
                        word.confidence for word in page.words
                        if word.confidence is not None
                    ]
                    if word_confidences:
                        page_confidences.append(sum(word_confidences) / len(word_confidences))
                    else:
                        page_confidences.append(0.95)
                else:
                    page_confidences.append(0.95)

            full_text = "\n\n".join(full_text_parts)
            avg_confidence = sum(page_confidences) / len(page_confidences) if page_confidences else 0.0
            page_count = len(result.pages)

            # Extract tables
            tables = self._extract_tables(result)

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "Azure Form Recognizer processing complete",
                page_count=page_count,
                text_length=len(full_text),
                confidence=avg_confidence,
                processing_time_ms=processing_time
            )

            return OCRResult(
                success=True,
                text=full_text,
                confidence=avg_confidence,
                provider=self.name,
                page_count=page_count,
                tables=tables,
                page_confidences=page_confidences,
                page_texts=page_texts,
                processing_time_ms=processing_time
            )

        except Exception as e:
            logger.error("Azure Form Recognizer error", error=str(e))
            return OCRResult(
                success=False,
                provider=self.name,
                error=f"Azure error: {str(e)}",
                processing_time_ms=int((time.time() - start_time) * 1000)
            )

    def _extract_tables(self, result) -> List[Dict[str, Any]]:
        """Extract tables from the analysis result"""
        tables = []

        if not hasattr(result, 'tables'):
            return tables

        for table_idx, table in enumerate(result.tables):
            extracted_table = {
                "table_index": table_idx,
                "row_count": table.row_count,
                "column_count": table.column_count,
                "rows": [],
                "header_rows": [],
            }

            # Organize cells by row
            rows: Dict[int, List[str]] = {}
            for cell in table.cells:
                row_idx = cell.row_index
                if row_idx not in rows:
                    rows[row_idx] = [""] * table.column_count
                rows[row_idx][cell.column_index] = cell.content

            # Separate headers and body
            sorted_rows = sorted(rows.items())
            for row_idx, row_cells in sorted_rows:
                if row_idx == 0:
                    extracted_table["header_rows"].append(row_cells)
                else:
                    extracted_table["rows"].append(row_cells)

            tables.append(extracted_table)

        return tables

    async def close(self):
        """Close the client connection"""
        if self._client:
            await self._client.close()
            self._client = None
