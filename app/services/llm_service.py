"""
LLM Service using OpenAI GPT-4
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID
import json
import structlog
from openai import AsyncOpenAI

from app.core.config import settings

logger = structlog.get_logger()


@dataclass
class AnalysisResult:
    """Result from LLM analysis"""
    risk_score: int
    risk_level: str
    summary_en: str
    summary_hi: str
    plain_english: str
    metadata: dict
    action_items: list[dict] = field(default_factory=list)
    required_documents: list[dict] = field(default_factory=list)
    legal_references: list[dict] = field(default_factory=list)
    confidence_scores: dict = field(default_factory=dict)


class LLMService:
    """Service for LLM-based notice analysis using OpenAI"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def analyze_notice(self, text: str, notice_id: UUID) -> AnalysisResult:
        """
        Analyze a GST notice using GPT-4

        Args:
            text: OCR-extracted text from the notice
            notice_id: UUID of the notice

        Returns:
            AnalysisResult with comprehensive analysis
        """
        logger.info("Starting LLM analysis", notice_id=str(notice_id))

        system_prompt = self._get_analysis_system_prompt()
        user_prompt = self._get_analysis_user_prompt(text)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            return AnalysisResult(
                risk_score=result.get("risk_score", 50),
                risk_level=result.get("risk_level", "medium"),
                summary_en=result.get("summary_en", ""),
                summary_hi=result.get("summary_hi", ""),
                plain_english=result.get("plain_english", ""),
                metadata=result.get("metadata", {}),
                action_items=result.get("action_items", []),
                required_documents=result.get("required_documents", []),
                legal_references=result.get("legal_references", []),
                confidence_scores=result.get("confidence_scores", {})
            )

        except Exception as e:
            logger.error("LLM analysis failed", notice_id=str(notice_id), error=str(e))
            raise

    async def generate_response_draft(
        self,
        notice_id: UUID,
        context: Optional[dict] = None
    ) -> str:
        """Generate a draft response for a notice"""
        logger.info("Generating response draft", notice_id=str(notice_id))

        # TODO: Fetch notice details and AI report from database
        # For now, return a placeholder

        system_prompt = """You are an expert GST consultant helping draft responses to GST notices.
        Generate a professional, legally sound response that addresses all points in the notice.
        The response should be in formal English, suitable for submission to tax authorities."""

        user_prompt = f"""Generate a draft response for notice {notice_id}.
        Context: {json.dumps(context) if context else 'No additional context provided'}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error("Response generation failed", notice_id=str(notice_id), error=str(e))
            raise

    def _get_analysis_system_prompt(self) -> str:
        """Get the system prompt for notice analysis"""
        return """You are an expert GST (Goods and Services Tax) analyst specializing in Indian tax law.
Your task is to analyze GST notices and provide comprehensive, accurate analysis.

CRITICAL RULES:
1. NEVER invent or guess information not present in the notice
2. Extract dates, amounts, and references ONLY from the actual text
3. If information is unclear, indicate low confidence
4. All legal references must be actual GST sections/rules

Provide your analysis in JSON format with the following structure:
{
    "risk_score": <0-100>,
    "risk_level": "<low|medium|high|critical>",
    "summary_en": "<2-3 sentence executive summary>",
    "summary_hi": "<Hindi summary - simple language>",
    "plain_english": "<Explanation as if explaining to a 15-year-old>",
    "metadata": {
        "notice_type": "<DRC-01, ASMT-10, etc.>",
        "notice_category": "<assessment|demand|registration|audit|refund>",
        "notice_number": "<extracted notice number>",
        "gstin": "<15-digit GSTIN>",
        "issue_date": "<YYYY-MM-DD>",
        "response_deadline": "<YYYY-MM-DD>",
        "tax_amount": <number>,
        "penalty_amount": <number>,
        "interest_amount": <number>,
        "period_from": "<YYYY-MM-DD>",
        "period_to": "<YYYY-MM-DD>",
        "issuing_authority": "<authority name>"
    },
    "action_items": [
        {
            "priority": <1-10>,
            "action": "<action title>",
            "description": "<detailed description>",
            "due_in_days": <number>,
            "assignee_suggestion": "<owner|accountant|ca>"
        }
    ],
    "required_documents": [
        {"document": "<document name>", "mandatory": <true|false>}
    ],
    "legal_references": [
        {"section": "<Section X>", "description": "<what it means>"}
    ],
    "confidence_scores": {
        "notice_type": <0-100>,
        "deadline": <0-100>,
        "amount": <0-100>,
        "overall": <0-100>
    }
}"""

    def _get_analysis_user_prompt(self, text: str) -> str:
        """Get the user prompt for notice analysis"""
        return f"""Analyze the following GST notice and provide a comprehensive analysis:

--- NOTICE TEXT ---
{text}
--- END NOTICE TEXT ---

Provide your analysis in the specified JSON format. Be thorough but accurate.
Only include information that is explicitly present in or can be reasonably inferred from the notice."""
