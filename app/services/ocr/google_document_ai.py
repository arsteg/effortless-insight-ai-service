"""
Google Document AI OCR provider
"""

import time
from typing import Optional, List, Dict, Any
import structlog

from google.cloud import documentai_v1 as documentai
from google.api_core.exceptions import GoogleAPIError

from app.core.config import settings
from app.services.ocr.base import OCRProvider, OCRResult

logger = structlog.get_logger()


class GoogleDocumentAI(OCRProvider):
    """Google Document AI OCR provider"""

    def __init__(self):
        self.project_id = settings.google_cloud_project_id
        self.location = settings.google_cloud_location
        self.processor_id = settings.google_document_ai_processor_id
        self._client: Optional[documentai.DocumentProcessorServiceAsyncClient] = None

    @property
    def name(self) -> str:
        return "google_document_ai"

    async def _get_client(self) -> documentai.DocumentProcessorServiceAsyncClient:
        """Get or create the Document AI client"""
        if self._client is None:
            self._client = documentai.DocumentProcessorServiceAsyncClient()
        return self._client

    async def is_available(self) -> bool:
        """Check if Google Document AI is configured"""
        return bool(
            self.project_id
            and self.processor_id
            and self.location
        )

    async def process_document(self, content: bytes, mime_type: str) -> OCRResult:
        """
        Process document using Google Document AI

        Args:
            content: Document content as bytes
            mime_type: MIME type (application/pdf, image/png, etc.)

        Returns:
            OCRResult with extracted text
        """
        start_time = time.time()

        if not await self.is_available():
            return OCRResult(
                success=False,
                provider=self.name,
                error="Google Document AI is not configured"
            )

        try:
            client = await self._get_client()

            # Build the processor name
            processor_name = (
                f"projects/{self.project_id}"
                f"/locations/{self.location}"
                f"/processors/{self.processor_id}"
            )

            # Create the document
            raw_document = documentai.RawDocument(
                content=content,
                mime_type=mime_type
            )

            # Create the request
            request = documentai.ProcessRequest(
                name=processor_name,
                raw_document=raw_document
            )

            # Process the document
            logger.info(
                "Processing document with Google Document AI",
                processor=processor_name,
                mime_type=mime_type,
                content_size=len(content)
            )

            result = await client.process_document(request=request)
            document = result.document

            # Extract text and confidence
            full_text = document.text
            page_count = len(document.pages)

            # Calculate average confidence across all pages
            page_confidences = []
            page_texts = []

            for page in document.pages:
                # Get page text using layout
                page_text = self._extract_page_text(document.text, page.layout)
                page_texts.append(page_text)

                # Calculate page confidence
                if page.layout and page.layout.confidence:
                    page_confidences.append(page.layout.confidence)
                else:
                    # Calculate from blocks if layout confidence not available
                    block_confidences = []
                    for block in page.blocks:
                        if block.layout and block.layout.confidence:
                            block_confidences.append(block.layout.confidence)
                    if block_confidences:
                        page_confidences.append(sum(block_confidences) / len(block_confidences))
                    else:
                        page_confidences.append(0.95)  # Default high confidence

            avg_confidence = sum(page_confidences) / len(page_confidences) if page_confidences else 0.0

            # Extract tables
            tables = self._extract_tables(document)

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "Google Document AI processing complete",
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

        except GoogleAPIError as e:
            logger.error("Google Document AI error", error=str(e))
            return OCRResult(
                success=False,
                provider=self.name,
                error=f"Google API error: {str(e)}",
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            logger.error("Unexpected error in Google Document AI", error=str(e))
            return OCRResult(
                success=False,
                provider=self.name,
                error=f"Unexpected error: {str(e)}",
                processing_time_ms=int((time.time() - start_time) * 1000)
            )

    def _extract_page_text(self, full_text: str, layout) -> str:
        """Extract text for a specific page from the full document text"""
        if not layout or not layout.text_anchor or not layout.text_anchor.text_segments:
            return ""

        text_parts = []
        for segment in layout.text_anchor.text_segments:
            start = int(segment.start_index) if segment.start_index else 0
            end = int(segment.end_index) if segment.end_index else len(full_text)
            text_parts.append(full_text[start:end])

        return "".join(text_parts)

    def _extract_tables(self, document) -> List[Dict[str, Any]]:
        """Extract tables from the document"""
        tables = []

        for page_idx, page in enumerate(document.pages):
            for table_idx, table in enumerate(page.tables):
                extracted_table = {
                    "page": page_idx + 1,
                    "table_index": table_idx,
                    "rows": [],
                    "header_rows": [],
                }

                # Extract header rows
                for header_row in table.header_rows:
                    row_cells = []
                    for cell in header_row.cells:
                        cell_text = self._extract_page_text(document.text, cell.layout)
                        row_cells.append(cell_text.strip())
                    extracted_table["header_rows"].append(row_cells)

                # Extract body rows
                for body_row in table.body_rows:
                    row_cells = []
                    for cell in body_row.cells:
                        cell_text = self._extract_page_text(document.text, cell.layout)
                        row_cells.append(cell_text.strip())
                    extracted_table["rows"].append(row_cells)

                tables.append(extracted_table)

        return tables
