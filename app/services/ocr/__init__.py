"""
OCR services for document processing
"""

from app.services.ocr.base import OCRProvider, OCRResult
from app.services.ocr.google_document_ai import GoogleDocumentAI
from app.services.ocr.azure_form_recognizer import AzureFormRecognizer
from app.services.ocr.ocr_service import OCRService

__all__ = [
    "OCRProvider",
    "OCRResult",
    "GoogleDocumentAI",
    "AzureFormRecognizer",
    "OCRService",
]
