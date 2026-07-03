"""
Notice analyzer using LLM
"""

import json
from typing import Optional, Dict, Any
import structlog

from app.services.llm.client import LLMClient
from app.services.llm.prompts import PromptTemplates
from app.services.llm.translator import HindiTranslator
from app.schemas.internal import AnalysisOutput, RAGContext

logger = structlog.get_logger()


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
            # Format RAG context
            context_str = PromptTemplates.format_rag_context(rag_context) if rag_context else ""

            # Truncate notice if too long
            text = notice_text[:15000] if len(notice_text) > 15000 else notice_text

            messages = [
                {"role": "system", "content": PromptTemplates.ANALYSIS_SYSTEM},
                {"role": "user", "content": PromptTemplates.ANALYSIS_USER.format(
                    notice_text=text,
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

            return AnalysisOutput(
                success=True,
                risk_score=result.get("risk_score", 50),
                risk_level=result.get("risk_level", "medium"),
                summary_en=result.get("summary_en", ""),
                summary_hi=summary_hi,
                plain_english=result.get("plain_english", ""),
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

            # Build additional points section
            additional_points = ""
            if points_to_address:
                additional_points += "\nSPECIFIC POINTS TO ADDRESS:\n"
                for point in points_to_address[:10]:  # Limit to 10
                    additional_points += f"- {point}\n"

            if additional_instructions:
                additional_points += f"\nADDITIONAL INSTRUCTIONS:\n{additional_instructions[:1000]}\n"

            messages = [
                {"role": "system", "content": PromptTemplates.RESPONSE_GENERATION_SYSTEM},
                {"role": "user", "content": PromptTemplates.RESPONSE_GENERATION_USER.format(
                    notice_summary=notice_summary,
                    notice_type=notice_type or "Unknown",
                    deadline=deadline or "Not specified",
                    key_issues=key_issues or "See notice summary",
                    context=context or "None provided",
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
        risk_factors: list,
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
            messages = [
                {"role": "system", "content": PromptTemplates.RISK_EXPLANATION_SYSTEM},
                {"role": "user", "content": PromptTemplates.RISK_EXPLANATION_USER.format(
                    risk_score=risk_score,
                    risk_level=risk_level,
                    risk_factors="\n".join(f"- {f}" for f in risk_factors),
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
