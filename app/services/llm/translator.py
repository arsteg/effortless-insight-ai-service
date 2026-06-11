"""
Hindi translator using LLM
"""

from typing import Optional
import structlog

from app.services.llm.client import LLMClient
from app.services.llm.prompts import PromptTemplates

logger = structlog.get_logger()


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

            messages = [
                {"role": "system", "content": PromptTemplates.TRANSLATION_SYSTEM},
                {"role": "user", "content": PromptTemplates.TRANSLATION_USER.format(
                    text=text
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

    async def translate_batch(self, texts: list, max_batch_size: int = 5) -> list:
        """
        Translate multiple texts to Hindi

        Args:
            texts: List of English texts
            max_batch_size: Maximum texts to combine in one request

        Returns:
            List of Hindi translations
        """
        translations = []

        for i in range(0, len(texts), max_batch_size):
            batch = texts[i:i + max_batch_size]

            # Combine texts with markers
            combined = "\n\n---\n\n".join(f"[{j+1}] {t}" for j, t in enumerate(batch))

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
                    import re
                    clean = re.sub(r'^\s*\[\d+\]\s*', '', part.strip())
                    if clean:
                        translations.append(clean)

            except Exception as e:
                logger.error("Batch translation failed", error=str(e))
                translations.extend([""] * len(batch))

        return translations
