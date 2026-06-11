"""
Base OCR provider interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class OCRResult:
    """Result from OCR processing"""
    success: bool
    text: str = ""
    confidence: float = 0.0
    provider: str = ""
    page_count: int = 0
    tables: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    # Per-page details
    page_confidences: List[float] = field(default_factory=list)
    page_texts: List[str] = field(default_factory=list)

    # Metadata
    processing_time_ms: int = 0
    raw_response: Optional[Dict[str, Any]] = None


class OCRProvider(ABC):
    """Abstract base class for OCR providers"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Get provider name"""
        pass

    @abstractmethod
    async def process_document(self, content: bytes, mime_type: str) -> OCRResult:
        """
        Process a document and extract text

        Args:
            content: Document content as bytes
            mime_type: MIME type of the document

        Returns:
            OCRResult with extracted text and metadata
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is available and configured"""
        pass
