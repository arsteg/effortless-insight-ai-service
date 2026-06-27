"""
Notice classifier using LLM
"""

import json
from typing import Optional
import structlog

from app.services.llm.client import LLMClient
from app.services.llm.prompts import PromptTemplates
from app.schemas.internal import ClassificationOutput

logger = structlog.get_logger()


class NoticeClassifier:
    """
    Classify GST notices using LLM

    Determines notice type (DRC-01, ASMT-10, etc.) and category.
    """

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()

    async def classify(self, notice_text: str) -> ClassificationOutput:
        """
        Classify a GST notice

        Args:
            notice_text: Full notice text (or relevant portion)

        Returns:
            ClassificationOutput with type and category
        """
        logger.info("Classifying notice", text_length=len(notice_text))

        try:
            # Truncate text if too long
            text = notice_text[:10000] if len(notice_text) > 10000 else notice_text

            messages = [
                {"role": "system", "content": PromptTemplates.CLASSIFICATION_SYSTEM},
                {"role": "user", "content": PromptTemplates.CLASSIFICATION_USER.format(
                    notice_text=text
                )}
            ]

            response = await self.client.complete(
                messages=messages,
                temperature=0.1,
                max_tokens=500,
                json_mode=True,
            )

            # Parse response
            result = json.loads(response["content"])

            logger.info(
                "Notice classified",
                notice_type=result.get("notice_type"),
                category=result.get("notice_category"),
                confidence=result.get("confidence")
            )

            return ClassificationOutput(
                success=True,
                notice_type=result.get("notice_type"),
                notice_category=result.get("notice_category"),
                sub_category=result.get("sub_category"),
                confidence=result.get("confidence", 0.8),
                all_classifications=[result],
            )

        except json.JSONDecodeError as e:
            logger.error("Failed to parse classification response", error=str(e))
            return ClassificationOutput(
                success=False,
                error=f"Invalid JSON response: {str(e)}",
            )

        except Exception as e:
            logger.error("Classification failed", error=str(e))
            return ClassificationOutput(
                success=False,
                error=str(e),
            )

    async def quick_classify(self, notice_text: str) -> tuple:
        """
        Quick classification using pattern matching first

        Falls back to LLM if patterns don't match.

        Returns:
            Tuple of (notice_type, category, confidence)
        """
        # Try pattern matching first
        notice_type = self._pattern_classify(notice_text)
        if notice_type:
            category = self._type_to_category(notice_type)
            return notice_type, category, 0.9

        # Fall back to LLM
        result = await self.classify(notice_text)
        if result.success:
            return result.notice_type, result.notice_category, result.confidence

        return None, "other", 0.5

    def _pattern_classify(self, text: str) -> Optional[str]:
        """
        Try to classify using regex patterns.

        Supports 100+ GST form types across all categories:
        - Demand & Recovery (DRC-01 to DRC-25)
        - Assessment (ASMT-01 to ASMT-18)
        - Registration (REG-01 to REG-31)
        - Audit (ADT-01 to ADT-04)
        - Returns (GSTR-1 to GSTR-11, RET-01 to RET-03)
        - Refund (RFD-01 to RFD-11)
        - Appeal (APL-01 to APL-08)
        - Inspection (INS-01 to INS-05)
        - E-Way Bill (EWB-01 to EWB-04, MOV-01 to MOV-11)
        - ITC (ITC-01 to ITC-04, PMT-01 to PMT-09)
        - Composition (CMP-01 to CMP-08)
        """
        import re
        from app.services.llm.notice_patterns import ALL_PATTERNS

        text_upper = text.upper()

        # Try all patterns from the comprehensive patterns module
        for pattern, notice_type, category, description in ALL_PATTERNS:
            if re.search(pattern, text_upper, re.IGNORECASE):
                logger.debug(
                    "Pattern matched",
                    pattern=pattern,
                    notice_type=notice_type,
                    category=category
                )
                return notice_type

        return None

    def _type_to_category(self, notice_type: str) -> str:
        """Map notice type to category using comprehensive mapping"""
        from app.services.llm.notice_patterns import TYPE_TO_CATEGORY
        return TYPE_TO_CATEGORY.get(notice_type, "other")
