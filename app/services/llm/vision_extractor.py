"""
Vision-LLM extraction: sends document page images to a multimodal model.

Scanned notices often contain handwriting, stamps, mixed Hindi/English text and
skewed layouts that plain OCR mangles. A vision model reads the page images
directly, so it recovers fields (e.g. a handwritten CBIC DIN) and the correct
reading order that OCR loses.
"""

import base64
import json
import re
from typing import List, Optional, Tuple
import structlog

from app.core.config import settings
from app.schemas.internal import VisionExtractionOutput
from app.services.llm.client import LLMClient
from app.services.llm.prompts import PromptTemplates
from app.services.image.pdf_splitter import PDFSplitter

logger = structlog.get_logger()


class VisionExtractor:
    """Extracts a transcript and structured fields from document page images"""

    def __init__(self, client: Optional[LLMClient] = None):
        model = settings.vision_model or settings.openai_model
        self.client = client or LLMClient(model=model)
        self.pdf_splitter = PDFSplitter(dpi=settings.vision_dpi)
        self.max_pages = settings.vision_max_pages

    async def extract(self, content: bytes, mime_type: str) -> VisionExtractionOutput:
        """
        Extract transcript + structured metadata from a document.

        Args:
            content: Document bytes (PDF or image)
            mime_type: MIME type of the document

        Returns:
            VisionExtractionOutput with transcript and metadata
        """
        if not settings.openai_api_key:
            return VisionExtractionOutput(
                success=False,
                error="Vision extraction unavailable: OpenAI API key not configured",
            )

        try:
            images = await self._to_page_images(content, mime_type)
        except Exception as e:
            logger.error("Vision extraction: page conversion failed", error=str(e))
            return VisionExtractionOutput(
                success=False,
                error=f"Page conversion failed: {e}",
            )

        if not images:
            return VisionExtractionOutput(success=False, error="No pages to process")

        page_count = len(images)
        if page_count > self.max_pages:
            logger.warning(
                "Vision extraction: page limit exceeded, truncating",
                page_count=page_count,
                max_pages=self.max_pages,
            )
            images = images[: self.max_pages]

        image_parts = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img_mime};base64,{base64.b64encode(img).decode()}",
                    "detail": "high",
                },
            }
            for img, img_mime in images
        ]

        messages = [
            {"role": "system", "content": PromptTemplates.VISION_EXTRACTION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": PromptTemplates.VISION_EXTRACTION_USER.format(
                            page_count=len(images)
                        ),
                    },
                    *image_parts,
                ],
            },
        ]

        try:
            response = await self.client.complete(
                messages=messages,
                temperature=0.0,
                max_tokens=4096,
                json_mode=True,
                use_cache=False,
            )
        except Exception as e:
            logger.error("Vision extraction: LLM call failed", error=str(e))
            return VisionExtractionOutput(success=False, error=str(e))

        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError as e:
            # Typically means the transcript hit the output token limit
            logger.error(
                "Vision extraction: invalid JSON response",
                error=str(e),
                finish_reason=response.get("finish_reason"),
            )
            return VisionExtractionOutput(
                success=False,
                error=f"Invalid JSON response: {e}",
                input_tokens=response.get("input_tokens", 0),
                output_tokens=response.get("output_tokens", 0),
            )

        metadata = result.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        if metadata.get("din"):
            metadata["din"] = self._normalize_din(str(metadata["din"]))

        handwritten = result.get("handwritten_fields")
        if not isinstance(handwritten, list):
            handwritten = []

        output = VisionExtractionOutput(
            success=True,
            transcript=result.get("transcript") or "",
            metadata=metadata,
            handwritten_fields=[str(f) for f in handwritten],
            page_count=page_count,
            pages_processed=len(images),
            input_tokens=response.get("input_tokens", 0),
            output_tokens=response.get("output_tokens", 0),
        )

        logger.info(
            "Vision extraction complete",
            pages_processed=output.pages_processed,
            transcript_length=len(output.transcript),
            fields_found=sum(1 for v in metadata.values() if v),
            handwritten_fields=output.handwritten_fields,
        )
        return output

    async def _to_page_images(
        self, content: bytes, mime_type: str
    ) -> List[Tuple[bytes, str]]:
        """Convert a document to a list of (image_bytes, mime_type) per page"""
        mime = (mime_type or "").lower()

        if "pdf" in mime:
            pages = await self.pdf_splitter.convert_to_images(content)
            return [(p, "image/png") for p in pages]

        if mime.startswith("image/"):
            return [(content, mime)]

        # Unknown content type: try PDF conversion, else treat as an image
        try:
            pages = await self.pdf_splitter.convert_to_images(content)
            return [(p, "image/png") for p in pages]
        except Exception:
            return [(content, "image/png")]

    @staticmethod
    def _normalize_din(din: str) -> Optional[str]:
        """Strip separators the model may echo from the document"""
        normalized = re.sub(r"[^A-Z0-9]", "", din.upper())
        return normalized or None
