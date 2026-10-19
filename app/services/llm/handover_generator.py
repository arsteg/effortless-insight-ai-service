"""
Handover summary generator service.
"""

import json
import time
from typing import Dict, Any
import structlog

from app.schemas.handover import HandoverRequest, HandoverSummary, HandoverResponse
from app.services.llm.prompts import PromptTemplates
from app.services.llm.client import LLMClient

logger = structlog.get_logger()


class HandoverGenerator:
    """
    Generates handover summaries for case transfers using LLM.
    """

    def __init__(self):
        self.llm_client = LLMClient()

    async def generate(self, request: HandoverRequest) -> HandoverResponse:
        """
        Generate a handover summary for a notice.

        Args:
            request: HandoverRequest with notice details and activity history

        Returns:
            HandoverResponse with the generated summary
        """
        start_time = time.time()

        logger.info(
            "Generating handover summary",
            notice_id=request.notice_id,
            has_activity_history=len(request.activity_history) > 0
        )

        try:
            # Format activity history
            activity_text = self._format_activity_history(request.activity_history)

            # Build the prompt
            user_prompt = PromptTemplates.HANDOVER_SUMMARY_USER.format(
                notice_id=request.notice_id,
                notice_type=request.notice_type or "Unknown",
                notice_category=request.notice_category or "Unknown",
                current_status=request.current_status or "Unknown",
                risk_level=request.risk_level or "Not assessed",
                response_deadline=request.response_deadline or "Not specified",
                assigned_to=request.assigned_to or "Unassigned",
                notice_summary=request.notice_summary or "No AI summary available",
                activity_history=activity_text or "No activity history available",
                additional_context=request.additional_context or "None provided",
            )

            # Call LLM
            response = await self.llm_client.complete(
                messages=[
                    {"role": "system", "content": PromptTemplates.HANDOVER_SUMMARY_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                json_mode=True,
                temperature=0.3,  # Lower temperature for more consistent output
                max_tokens=1500,
            )

            # Parse the response
            summary = self._parse_response(response["content"])

            processing_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Handover summary generated",
                notice_id=request.notice_id,
                processing_time_ms=processing_time_ms
            )

            return HandoverResponse(
                success=True,
                summary=summary,
                processing_time_ms=processing_time_ms
            )

        except Exception as e:
            logger.error(
                "Failed to generate handover summary",
                notice_id=request.notice_id,
                error=str(e)
            )
            return HandoverResponse(
                success=False,
                error=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000)
            )

    def _format_activity_history(self, activities: list) -> str:
        """Format activity history for the prompt."""
        if not activities:
            return "No activity history available"

        lines = []
        for activity in activities[-10:]:  # Limit to last 10 activities
            action = activity.get("action", "Unknown action")
            user = activity.get("user", "Unknown user")
            date = activity.get("date", "Unknown date")
            lines.append(f"- {date}: {action} (by {user})")

        return "\n".join(lines)

    def _parse_response(self, content: str) -> HandoverSummary:
        """Parse LLM response into HandoverSummary."""
        try:
            # Try to extract JSON from the response
            # Handle cases where LLM might include markdown code blocks
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            return HandoverSummary(
                background=data.get("background", ""),
                work_completed=data.get("work_completed", []),
                pending_items=data.get("pending_items", []),
                next_steps=data.get("next_steps", []),
                key_deadlines=data.get("key_deadlines", []),
                key_contacts=data.get("key_contacts", []),
                risk_summary=data.get("risk_summary"),
            )

        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract key information from text
            logger.warning("Failed to parse handover summary as JSON, creating fallback")
            return HandoverSummary(
                background=content[:500] if content else "Unable to generate summary",
                work_completed=[],
                pending_items=["Review the notice and determine next steps"],
                next_steps=["Analyze the notice details", "Prepare response if required"],
                key_deadlines=[],
                key_contacts=[],
                risk_summary="Risk assessment requires manual review",
            )
