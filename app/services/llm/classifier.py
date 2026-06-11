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
        """Try to classify using regex patterns"""
        import re

        patterns = {
            r'DRC[\-\s]?01': "DRC-01",
            r'DRC[\-\s]?07': "DRC-07",
            r'DRC[\-\s]?13': "DRC-13",
            r'ASMT[\-\s]?10': "ASMT-10",
            r'ASMT[\-\s]?12': "ASMT-12",
            r'ASMT[\-\s]?14': "ASMT-14",
            r'REG[\-\s]?17': "REG-17",
            r'REG[\-\s]?19': "REG-19",
            r'ADT[\-\s]?01': "ADT-01",
            r'GSTR[\-\s]?3A': "GSTR-3A",
            r'RET[\-\s]?01': "RET-01",
        }

        text_upper = text.upper()
        for pattern, notice_type in patterns.items():
            if re.search(pattern, text_upper, re.IGNORECASE):
                return notice_type

        return None

    def _type_to_category(self, notice_type: str) -> str:
        """Map notice type to category"""
        mapping = {
            "DRC-01": "demand",
            "DRC-07": "demand",
            "DRC-13": "demand",
            "ASMT-10": "assessment",
            "ASMT-12": "assessment",
            "ASMT-14": "assessment",
            "REG-17": "registration",
            "REG-19": "registration",
            "ADT-01": "audit",
            "GSTR-3A": "returns",
            "RET-01": "returns",
        }
        return mapping.get(notice_type, "other")
