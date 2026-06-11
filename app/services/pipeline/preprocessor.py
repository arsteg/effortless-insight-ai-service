"""
Preprocessor stage for the pipeline
"""

import time
from typing import Tuple
import structlog
import httpx

from app.schemas.internal import PipelineContext
from app.services.image.quality_assessor import QualityAssessor
from app.services.image.pdf_splitter import PDFSplitter

logger = structlog.get_logger()


class Preprocessor:
    """
    Stage 1: Preprocessing

    Responsibilities:
    - Download document from S3
    - Detect file format
    - Assess quality
    - Prepare for OCR
    """

    def __init__(self):
        self.quality_assessor = QualityAssessor()
        self.pdf_splitter = PDFSplitter()

    async def process(self, context: PipelineContext) -> PipelineContext:
        """
        Run preprocessing stage

        Args:
            context: Pipeline context with file_url

        Returns:
            Updated context with downloaded content and quality info
        """
        start_time = time.time()
        context.current_stage = "preprocessing"

        logger.info(
            "Starting preprocessing",
            notice_id=str(context.notice_id),
            file_url=context.file_url[:50] + "..."
        )

        try:
            # Download document
            content, mime_type = await self._download_document(context.file_url)
            if content is None:
                context.mark_failed("preprocessing", f"Download failed: {mime_type}")
                return context

            context.file_size = len(content)
            context.file_type = self._get_file_type(mime_type)

            logger.info(
                "Document downloaded",
                notice_id=str(context.notice_id),
                size=context.file_size,
                type=context.file_type
            )

            # Assess quality for images
            if context.file_type == "image":
                assessment = await self.quality_assessor.assess(content)
                logger.info(
                    "Quality assessed",
                    score=assessment.overall_score,
                    acceptable=assessment.is_acceptable,
                    needs_preprocessing=assessment.needs_preprocessing
                )

            # Get PDF info
            elif context.file_type == "pdf":
                pdf_info = await self.pdf_splitter.get_pdf_info(content)
                logger.info(
                    "PDF info retrieved",
                    pages=pdf_info.get("page_count", 0),
                    has_text=pdf_info.get("has_embedded_text", False)
                )

            # Store content in context for next stage
            # Note: In production, might store to temp file instead
            context._document_content = content
            context._mime_type = mime_type

            duration_ms = int((time.time() - start_time) * 1000)
            context.record_stage_time("preprocessing", duration_ms)

            logger.info(
                "Preprocessing complete",
                notice_id=str(context.notice_id),
                duration_ms=duration_ms
            )

            return context

        except Exception as e:
            logger.error(
                "Preprocessing failed",
                notice_id=str(context.notice_id),
                error=str(e)
            )
            context.mark_failed("preprocessing", str(e))
            return context

    async def _download_document(self, url: str) -> Tuple[bytes, str]:
        """
        Download document from URL

        Returns:
            Tuple of (content, mime_type or error)
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                content = response.content
                content_type = response.headers.get('content-type', 'application/pdf')
                mime_type = content_type.split(';')[0].strip()

                return content, mime_type

        except httpx.TimeoutException:
            return None, "Download timeout"
        except httpx.HTTPStatusError as e:
            return None, f"HTTP error: {e.response.status_code}"
        except Exception as e:
            return None, str(e)

    def _get_file_type(self, mime_type: str) -> str:
        """Determine file type from MIME type"""
        mime_type = mime_type.lower()

        if 'pdf' in mime_type:
            return 'pdf'
        elif 'image' in mime_type:
            return 'image'
        elif 'tiff' in mime_type:
            return 'image'
        else:
            return 'unknown'
