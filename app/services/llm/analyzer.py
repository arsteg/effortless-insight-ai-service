"""
Notice analyzer using LLM

Security: All user inputs are sanitized to prevent prompt injection attacks.
See app.services.security.prompt_sanitizer for implementation details.
"""

import json
from typing import Optional, Dict, Any, List
import structlog

from app.core.config import settings
from app.services.llm.client import LLMClient
from app.services.llm.prompts import PromptTemplates
from app.services.llm.translator import HindiTranslator
from app.schemas.internal import AnalysisOutput, RAGContext
from app.services.security.prompt_sanitizer import (
    PromptSanitizer,
    sanitize_for_prompt,
    sanitize_user_input,
)

logger = structlog.get_logger()

# Initialize sanitizer for this module
_sanitizer = PromptSanitizer(strict_mode=True)


class NoticeAnalyzer:
    """
    Comprehensive notice analysis using LLM

    Provides:
    - Risk assessment
    - Summary generation
    - Action items
    - Document requirements
    - Legal references
    """

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()
        self.translator = HindiTranslator(self.client)

    async def analyze(
        self,
        notice_text: str,
        rag_context: Optional[RAGContext] = None,
        include_hindi: bool = True,
    ) -> AnalysisOutput:
        """
        Analyze a GST notice comprehensively

        Args:
            notice_text: Full notice text
            rag_context: Retrieved context for RAG
            include_hindi: Include Hindi translation

        Returns:
            AnalysisOutput with full analysis
        """
        logger.info("Analyzing notice", text_length=len(notice_text))

        try:
            # SECURITY: Sanitize user input to prevent prompt injection (CRIT-003)
            sanitization_result = _sanitizer.sanitize(notice_text, content_type="notice_text")
            if sanitization_result.injection_attempts_detected > 0:
                logger.warning(
                    "Potential prompt injection in notice text",
                    patterns=sanitization_result.patterns_matched,
                    confidence=sanitization_result.confidence_score
                )

            # Use sanitized text with XML delimiters for clear boundaries
            max_chars = settings.analysis_max_chars
            if len(sanitization_result.sanitized_text) > max_chars:
                logger.warning(
                    "Notice text truncated for analysis",
                    original_length=len(sanitization_result.sanitized_text),
                    max_chars=max_chars
                )
            sanitized_text = _sanitizer.wrap_user_content(
                sanitization_result.sanitized_text[:max_chars],
                label="NOTICE_CONTENT"
            )

            # Format and sanitize RAG context
            context_str = ""
            if rag_context:
                raw_context = PromptTemplates.format_rag_context(rag_context)
                # RAG context is from our knowledge base but still sanitize for safety
                context_str = sanitize_user_input(raw_context, content_type="context")

            messages = [
                {"role": "system", "content": PromptTemplates.ANALYSIS_SYSTEM},
                {"role": "user", "content": PromptTemplates.ANALYSIS_USER.format(
                    notice_text=sanitized_text,
                    rag_context=context_str if context_str else "No additional context available."
                )}
            ]

            response = await self.client.complete(
                messages=messages,
                temperature=0.2,
                max_tokens=4000,
                json_mode=True,
            )

            # Parse response
            result = json.loads(response["content"])

            # Generate Hindi translation if requested
            summary_hi = ""
            if include_hindi and result.get("summary_en"):
                summary_hi = await self.translator.translate(result["summary_en"])

            logger.info(
                "Notice analysis complete",
                risk_score=result.get("risk_score"),
                risk_level=result.get("risk_level"),
                input_tokens=response["input_tokens"],
                output_tokens=response["output_tokens"],
            )

            llm_metadata = result.get("metadata")

            return AnalysisOutput(
                success=True,
                risk_score=result.get("risk_score", 50),
                risk_level=result.get("risk_level", "medium"),
                summary_en=result.get("summary_en", ""),
                summary_hi=summary_hi,
                plain_english=result.get("plain_english", ""),
                metadata=llm_metadata if isinstance(llm_metadata, dict) else {},
                action_items=result.get("action_items", []),
                required_documents=result.get("required_documents", []),
                legal_references=result.get("legal_references", []),
                confidence_scores=result.get("confidence_scores", {}),
                input_tokens=response["input_tokens"],
                output_tokens=response["output_tokens"],
            )

        except json.JSONDecodeError as e:
            logger.error("Failed to parse analysis response", error=str(e))
            return AnalysisOutput(
                success=False,
                error=f"Invalid JSON response: {str(e)}",
            )

        except Exception as e:
            logger.error("Analysis failed", error=str(e))
            return AnalysisOutput(
                success=False,
                error=str(e),
            )

    async def generate_response_draft(
        self,
        notice_summary: str,
        notice_type: Optional[str] = None,
        deadline: Optional[str] = None,
        key_issues: Optional[str] = None,
        context: Optional[str] = None,
        tone: Optional[str] = None,
        language: Optional[str] = None,
        points_to_address: Optional[list] = None,
        additional_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a draft response for a notice

        Args:
            notice_summary: Summary of the notice
            notice_type: Type of notice
            deadline: Response deadline
            key_issues: Key issues to address
            context: Additional context
            tone: Response tone (formal, conciliatory, defensive)
            language: Response language (en, hi)
            points_to_address: Specific points to address
            additional_instructions: Additional instructions

        Returns:
            Dict with draft content and metadata
        """
        logger.info(
            "Generating response draft",
            tone=tone,
            language=language,
            has_points=bool(points_to_address),
        )

        try:
            # Get tone instruction
            tone_instruction = {
                "conciliatory": PromptTemplates.TONE_CONCILIATORY,
                "defensive": PromptTemplates.TONE_DEFENSIVE,
            }.get(tone or "formal", PromptTemplates.TONE_FORMAL)

            # Get language instruction
            language_instruction = (
                PromptTemplates.LANGUAGE_HINDI
                if language == "hi"
                else PromptTemplates.LANGUAGE_ENGLISH
            )

            # SECURITY: Sanitize all user-provided inputs (CRIT-003)
            # These inputs come from API requests and could contain injection attempts
            sanitized_summary = sanitize_user_input(notice_summary or "", content_type="summary")
            sanitized_issues = sanitize_user_input(key_issues or "", content_type="context")
            sanitized_context = sanitize_user_input(context or "", content_type="context")

            # Build and sanitize additional points section
            additional_points = ""
            if points_to_address:
                additional_points += "\nSPECIFIC POINTS TO ADDRESS:\n"
                for point in points_to_address[:10]:  # Limit to 10
                    # Sanitize each point individually
                    sanitized_point = sanitize_user_input(str(point), content_type="points")
                    additional_points += f"- {sanitized_point}\n"

            if additional_instructions:
                # This is a high-risk field - sanitize strictly
                sanitized_instructions = _sanitizer.sanitize(
                    additional_instructions[:1000],
                    content_type="instructions"
                )
                if sanitized_instructions.injection_attempts_detected > 0:
                    logger.warning(
                        "Potential injection in additional_instructions",
                        patterns=sanitized_instructions.patterns_matched
                    )
                additional_points += f"\nADDITIONAL INSTRUCTIONS:\n{sanitized_instructions.sanitized_text}\n"

            messages = [
                {"role": "system", "content": PromptTemplates.RESPONSE_GENERATION_SYSTEM},
                {"role": "user", "content": PromptTemplates.RESPONSE_GENERATION_USER.format(
                    notice_summary=sanitized_summary,
                    notice_type=notice_type or "Unknown",
                    deadline=deadline or "Not specified",
                    key_issues=sanitized_issues if sanitized_issues else "See notice summary",
                    context=sanitized_context if sanitized_context else "None provided",
                    tone=tone_instruction,
                    language_instruction=language_instruction,
                    additional_points=additional_points,
                )}
            ]

            response = await self.client.complete(
                messages=messages,
                temperature=0.3,
                max_tokens=4000,
            )

            logger.info(
                "Response draft generated",
                input_tokens=response.get("input_tokens", 0),
                output_tokens=response.get("output_tokens", 0),
            )

            return {
                "content": response["content"],
                "model": response.get("model", "unknown"),
                "input_tokens": response.get("input_tokens", 0),
                "output_tokens": response.get("output_tokens", 0),
            }

        except Exception as e:
            logger.error("Response generation failed", error=str(e))
            raise

    async def explain_risk(
        self,
        risk_score: int,
        risk_level: str,
        risk_factors: List[str],
    ) -> str:
        """
        Generate simple explanation of risk assessment

        Args:
            risk_score: Risk score (0-100)
            risk_level: Risk level (low/medium/high/critical)
            risk_factors: List of risk factor descriptions

        Returns:
            Plain language explanation
        """
        try:
            # SECURITY: Sanitize risk factors which may come from LLM output (chain injection)
            sanitized_factors = [
                sanitize_user_input(str(f), content_type="points")
                for f in (risk_factors or [])[:10]
            ]

            messages = [
                {"role": "system", "content": PromptTemplates.RISK_EXPLANATION_SYSTEM},
                {"role": "user", "content": PromptTemplates.RISK_EXPLANATION_USER.format(
                    risk_score=risk_score,
                    risk_level=risk_level,
                    risk_factors="\n".join(f"- {f}" for f in sanitized_factors),
                )}
            ]

            response = await self.client.complete(
                messages=messages,
                temperature=0.3,
                max_tokens=500,
            )

            return response["content"]

        except Exception as e:
            logger.error("Risk explanation failed", error=str(e))
            return f"This notice has a {risk_level} risk level ({risk_score}/100). Please review carefully."

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get LLM usage statistics"""
        return self.client.get_usage_stats()
