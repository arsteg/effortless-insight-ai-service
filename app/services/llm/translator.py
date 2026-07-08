"""
Hindi translator using LLM

Security: All user inputs are sanitized to prevent prompt injection attacks.
See app.services.security.prompt_sanitizer for implementation details.
"""

import re
from typing import Optional, List
import structlog

from app.services.llm.client import LLMClient
from app.services.llm.prompts import PromptTemplates
from app.services.security.prompt_sanitizer import PromptSanitizer, sanitize_user_input

logger = structlog.get_logger()

# Initialize sanitizer for this module
_sanitizer = PromptSanitizer(strict_mode=True)


class HindiTranslator:
    """
    Translate text to Hindi using LLM

    Optimized for legal/tax terminology.
    """

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()

    async def translate(self, text: str, max_length: int = 2000) -> str:
        """
        Translate text to Hindi

        Args:
            text: English text to translate
            max_length: Maximum length of input text

        Returns:
            Hindi translation
        """
        if not text:
            return ""

        try:
            # Truncate if necessary
            if len(text) > max_length:
                text = text[:max_length] + "..."

            # SECURITY: Sanitize input to prevent prompt injection (CRIT-003)
            sanitization_result = _sanitizer.sanitize(text, content_type="summary")
            if sanitization_result.injection_attempts_detected > 0:
                logger.warning(
                    "Potential prompt injection in translation input",
                    patterns=sanitization_result.patterns_matched
                )

            # Wrap with XML delimiters for clear boundaries
            sanitized_text = _sanitizer.wrap_user_content(
                sanitization_result.sanitized_text,
                label="TEXT_TO_TRANSLATE"
            )

            messages = [
                {"role": "system", "content": PromptTemplates.TRANSLATION_SYSTEM},
                {"role": "user", "content": PromptTemplates.TRANSLATION_USER.format(
                    text=sanitized_text
                )}
            ]

            response = await self.client.complete(
                messages=messages,
                temperature=0.2,
                max_tokens=1000,
            )

            translation = response["content"].strip()

            logger.debug(
                "Text translated to Hindi",
                input_length=len(text),
                output_length=len(translation)
            )

            return translation

        except Exception as e:
            logger.error("Translation failed", error=str(e))
            return ""

    async def translate_batch(self, texts: List[str], max_batch_size: int = 5) -> List[str]:
        """
        Translate multiple texts to Hindi

        Args:
            texts: List of English texts
            max_batch_size: Maximum texts to combine in one request

        Returns:
            List of Hindi translations
        """
        translations: List[str] = []

        for i in range(0, len(texts), max_batch_size):
            batch = texts[i:i + max_batch_size]

            # SECURITY: Sanitize each text in the batch (CRIT-003)
            sanitized_batch = []
            for t in batch:
                sanitized = sanitize_user_input(str(t), content_type="summary")
                sanitized_batch.append(sanitized)

            # Combine texts with markers and wrap in XML delimiters
            combined_parts = []
            for j, t in enumerate(sanitized_batch):
                combined_parts.append(f"[{j+1}] {t}")

            combined = _sanitizer.wrap_user_content(
                "\n\n---\n\n".join(combined_parts),
                label="TEXTS_TO_TRANSLATE"
            )

            try:
                messages = [
                    {"role": "system", "content": PromptTemplates.TRANSLATION_SYSTEM + "\n\nTranslate each numbered section separately, maintaining the numbering."},
                    {"role": "user", "content": PromptTemplates.TRANSLATION_USER.format(
                        text=combined
                    )}
                ]

                response = await self.client.complete(
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2000,
                )

                # Parse batch response
                result = response["content"]
                # Simple split - in production, use more robust parsing
                parts = result.split("---")
                for part in parts:
                    # Remove numbering and clean
                    clean = re.sub(r'^\s*\[\d+\]\s*', '', part.strip())
                    if clean:
                        translations.append(clean)

            except Exception as e:
                logger.error("Batch translation failed", error=str(e))
                translations.extend([""] * len(batch))

        return translations
