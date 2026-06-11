"""
PDF page splitting and conversion
"""

import io
from typing import List, Tuple, Optional
import structlog

logger = structlog.get_logger()


class PDFSplitter:
    """
    PDF processing utilities

    Handles splitting multi-page PDFs and converting pages to images.
    """

    def __init__(self, dpi: int = 200):
        self.dpi = dpi

    async def split_pages(self, pdf_bytes: bytes) -> List[bytes]:
        """
        Split PDF into individual page PDFs

        Args:
            pdf_bytes: Input PDF as bytes

        Returns:
            List of single-page PDF bytes
        """
        try:
            from pypdf import PdfReader, PdfWriter

            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages = []

            for page_num in range(len(reader.pages)):
                writer = PdfWriter()
                writer.add_page(reader.pages[page_num])

                output = io.BytesIO()
                writer.write(output)
                output.seek(0)
                pages.append(output.getvalue())

            logger.info("PDF split into pages", page_count=len(pages))
            return pages

        except Exception as e:
            logger.error("PDF split failed", error=str(e))
            raise

    async def convert_to_images(self, pdf_bytes: bytes) -> List[bytes]:
        """
        Convert PDF pages to images

        Args:
            pdf_bytes: Input PDF as bytes

        Returns:
            List of PNG image bytes for each page
        """
        try:
            from pdf2image import convert_from_bytes

            images = convert_from_bytes(
                pdf_bytes,
                dpi=self.dpi,
                fmt='png'
            )

            image_bytes_list = []
            for img in images:
                output = io.BytesIO()
                img.save(output, format='PNG')
                output.seek(0)
                image_bytes_list.append(output.getvalue())

            logger.info(
                "PDF converted to images",
                page_count=len(image_bytes_list),
                dpi=self.dpi
            )
            return image_bytes_list

        except Exception as e:
            logger.error("PDF to image conversion failed", error=str(e))
            raise

    async def get_page_count(self, pdf_bytes: bytes) -> int:
        """Get the number of pages in a PDF"""
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(pdf_bytes))
            return len(reader.pages)

        except Exception as e:
            logger.error("Failed to get page count", error=str(e))
            return 0

    async def extract_text_basic(self, pdf_bytes: bytes) -> str:
        """
        Basic text extraction from PDF (without OCR)

        Useful for PDFs with embedded text.

        Args:
            pdf_bytes: Input PDF

        Returns:
            Extracted text
        """
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(pdf_bytes))
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts)

        except Exception as e:
            logger.error("Basic text extraction failed", error=str(e))
            return ""

    async def get_pdf_info(self, pdf_bytes: bytes) -> dict:
        """Get PDF metadata and information"""
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(pdf_bytes))

            info = {
                "page_count": len(reader.pages),
                "is_encrypted": reader.is_encrypted,
                "size_bytes": len(pdf_bytes),
            }

            # Get metadata if available
            if reader.metadata:
                info["metadata"] = {
                    "title": reader.metadata.title,
                    "author": reader.metadata.author,
                    "creator": reader.metadata.creator,
                    "producer": reader.metadata.producer,
                    "creation_date": str(reader.metadata.creation_date) if reader.metadata.creation_date else None,
                }

            # Check if text is extractable (embedded fonts)
            has_text = False
            for page in reader.pages[:1]:  # Check first page only
                text = page.extract_text()
                if text and len(text.strip()) > 50:
                    has_text = True
                    break

            info["has_embedded_text"] = has_text

            return info

        except Exception as e:
            logger.error("Failed to get PDF info", error=str(e))
            return {
                "error": str(e),
                "size_bytes": len(pdf_bytes),
            }

    async def merge_pdfs(self, pdf_list: List[bytes]) -> bytes:
        """
        Merge multiple PDFs into one

        Args:
            pdf_list: List of PDF bytes to merge

        Returns:
            Merged PDF bytes
        """
        try:
            from pypdf import PdfWriter

            writer = PdfWriter()

            for pdf_bytes in pdf_list:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(pdf_bytes))
                for page in reader.pages:
                    writer.add_page(page)

            output = io.BytesIO()
            writer.write(output)
            output.seek(0)

            logger.info("PDFs merged", input_count=len(pdf_list), total_pages=len(writer.pages))
            return output.getvalue()

        except Exception as e:
            logger.error("PDF merge failed", error=str(e))
            raise
