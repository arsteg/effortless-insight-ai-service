"""
Report generator stage for the pipeline
"""

import time
from datetime import date
from typing import Optional
from uuid import UUID
import structlog

from app.schemas.internal import PipelineContext
from app.schemas.report import AIReport, RiskAssessment, ConfidenceScores, VerificationResult
from app.schemas.responses import (
    AiReportData, NoticeMetadata, ActionItem, RequiredDocument, LegalReference
)

logger = structlog.get_logger()


class ReportGenerator:
    """
    Stage 8: Report Generation

    Assembles all analysis results into the final report.
    """

    async def generate(self, context: PipelineContext) -> AIReport:
        """
        Generate final AI report from pipeline context

        Args:
            context: Completed pipeline context

        Returns:
            AIReport with all analysis results
        """
        start_time = time.time()
        context.current_stage = "report_generation"

        logger.info(
            "Generating report",
            notice_id=str(context.notice_id)
        )

        try:
            # Extract components
            analysis = context.analysis_output
            entities = context.entity_output.entities if context.entity_output else None
            verification = context.verification_output

            # Build metadata
            metadata = self._build_metadata(analysis, entities)

            # Build action items
            action_items = self._build_action_items(analysis)

            # Build required documents
            required_documents = self._build_required_documents(analysis)

            # Build legal references
            legal_references = self._build_legal_references(analysis)

            # Build confidence scores
            confidence_scores = self._build_confidence_scores(analysis, verification)

            # Build verification result
            verification_result = None
            if verification:
                verification_result = verification.verification

            # Assemble report
            report = AIReport(
                risk_score=analysis.risk_score if analysis else 50,
                risk_level=analysis.risk_level if analysis else "medium",
                summary_en=analysis.summary_en if analysis else "",
                summary_hi=analysis.summary_hi if analysis else "",
                plain_english=analysis.plain_english if analysis else "",
                metadata=metadata,
                action_items=action_items,
                required_documents=required_documents,
                legal_references=legal_references,
                confidence_scores=confidence_scores,
                verification=verification_result,
                processing_time_ms=context.get_total_time_ms(),
                model_used=context.analysis_output.model if hasattr(context.analysis_output, 'model') else None,
                ocr_confidence=context.ocr_output.confidence if context.ocr_output else None,
            )

            context.report = report

            duration_ms = int((time.time() - start_time) * 1000)
            context.record_stage_time("report_generation", duration_ms)

            logger.info(
                "Report generated",
                notice_id=str(context.notice_id),
                risk_score=report.risk_score,
                duration_ms=duration_ms
            )

            return report

        except Exception as e:
            logger.error(
                "Report generation failed",
                notice_id=str(context.notice_id),
                error=str(e)
            )
            raise

    def _build_metadata(self, analysis, entities) -> NoticeMetadata:
        """Build notice metadata from analysis and entities"""
        # Start with analysis metadata
        llm_metadata = analysis.metadata if analysis and hasattr(analysis, 'metadata') else {}
        if isinstance(llm_metadata, dict):
            pass
        else:
            llm_metadata = {}

        # Override with entity extraction where available (more reliable)
        return NoticeMetadata(
            notice_type=llm_metadata.get("notice_type"),
            notice_category=llm_metadata.get("notice_category"),
            notice_number=entities.notice_number if entities else llm_metadata.get("notice_number"),
            gstin=entities.primary_gstin if entities else llm_metadata.get("gstin"),
            issue_date=entities.issue_date if entities else self._parse_date(llm_metadata.get("issue_date")),
            response_deadline=entities.response_deadline if entities else self._parse_date(llm_metadata.get("response_deadline")),
            tax_amount=entities.tax_amount if entities else llm_metadata.get("tax_amount"),
            penalty_amount=entities.penalty_amount if entities else llm_metadata.get("penalty_amount"),
            interest_amount=entities.interest_amount if entities else llm_metadata.get("interest_amount"),
            period_from=entities.period_from if entities else self._parse_date(llm_metadata.get("period_from")),
            period_to=entities.period_to if entities else self._parse_date(llm_metadata.get("period_to")),
            issuing_authority=entities.issuing_authority if entities else llm_metadata.get("issuing_authority"),
        )

    def _build_action_items(self, analysis) -> list:
        """Build action items from analysis"""
        items = []

        if not analysis or not analysis.action_items:
            return items

        for item in analysis.action_items:
            if isinstance(item, dict):
                items.append(ActionItem(
                    priority=item.get("priority", 5),
                    action=item.get("action", ""),
                    description=item.get("description", ""),
                    due_in_days=item.get("due_in_days"),
                    assignee_suggestion=item.get("assignee_suggestion"),
                ))

        return items

    def _build_required_documents(self, analysis) -> list:
        """Build required documents list"""
        docs = []

        if not analysis or not analysis.required_documents:
            return docs

        for doc in analysis.required_documents:
            if isinstance(doc, dict):
                docs.append(RequiredDocument(
                    document=doc.get("document", ""),
                    mandatory=doc.get("mandatory", False),
                ))

        return docs

    def _build_legal_references(self, analysis) -> list:
        """Build legal references list"""
        refs = []

        if not analysis or not analysis.legal_references:
            return refs

        for ref in analysis.legal_references:
            if isinstance(ref, dict):
                refs.append(LegalReference(
                    section=ref.get("section", ""),
                    description=ref.get("description", ""),
                ))

        return refs

    def _build_confidence_scores(self, analysis, verification) -> ConfidenceScores:
        """Build confidence scores"""
        if not analysis or not analysis.confidence_scores:
            return ConfidenceScores()

        scores = analysis.confidence_scores
        if isinstance(scores, dict):
            return ConfidenceScores(
                notice_type=scores.get("notice_type", 0),
                deadline=scores.get("deadline", 0),
                amount=scores.get("amount", 0),
                gstin=scores.get("gstin", 0),
                risk_assessment=scores.get("risk_assessment", 0),
                overall=scores.get("overall", 0),
            )

        return ConfidenceScores()

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object"""
        if not date_str:
            return None

        try:
            from datetime import datetime
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    def to_api_response(self, report: AIReport) -> AiReportData:
        """Convert AIReport to API response format"""
        return report.to_ai_report_data()
