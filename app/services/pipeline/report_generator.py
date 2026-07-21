"""
Report generator stage for the pipeline
"""

import time
from datetime import date, datetime
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
            metadata = self._build_metadata(
                analysis,
                entities,
                vision=context.vision_output,
                classification=context.classification_output,
            )

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

    def _build_metadata(self, analysis, entities, vision=None, classification=None) -> NoticeMetadata:
        """
        Build notice metadata by merging all extraction sources per field.

        Precedence: validated regex entities first (checksum/format checked),
        then vision extraction (reads the actual page images, including
        handwriting), then LLM text analysis, then pattern classification.
        """
        llm_md = analysis.metadata if analysis and isinstance(getattr(analysis, "metadata", None), dict) else {}
        vision_md = vision.metadata if vision and vision.success and isinstance(vision.metadata, dict) else {}

        def pick(*values):
            for v in values:
                if v not in (None, "", "null"):
                    return v
            return None

        def ent(field):
            return getattr(entities, field, None) if entities else None

        classified_type = classification.notice_type if classification and classification.success else None
        classified_category = classification.notice_category if classification and classification.success else None

        return NoticeMetadata(
            notice_type=pick(classified_type, vision_md.get("notice_type"), llm_md.get("notice_type")),
            notice_category=pick(classified_category, llm_md.get("notice_category")),
            notice_number=pick(ent("notice_number"), vision_md.get("notice_number"), llm_md.get("notice_number")),
            gstin=pick(ent("primary_gstin"), vision_md.get("gstin"), llm_md.get("gstin")),
            # Dates prefer vision/LLM: the regex assigns date *types* from nearby
            # keywords, which scanned layouts frequently break
            issue_date=pick(
                self._parse_date(vision_md.get("issue_date")),
                self._parse_date(llm_md.get("issue_date")),
                ent("issue_date"),
            ),
            response_deadline=pick(
                self._parse_date(vision_md.get("response_deadline")),
                self._parse_date(llm_md.get("response_deadline")),
                ent("response_deadline"),
            ),
            tax_amount=pick(ent("tax_amount"), vision_md.get("tax_amount"), llm_md.get("tax_amount")),
            penalty_amount=pick(ent("penalty_amount"), vision_md.get("penalty_amount"), llm_md.get("penalty_amount")),
            interest_amount=pick(ent("interest_amount"), vision_md.get("interest_amount"), llm_md.get("interest_amount")),
            period_from=pick(
                self._parse_date(vision_md.get("period_from")),
                self._parse_date(llm_md.get("period_from")),
                ent("period_from"),
            ),
            period_to=pick(
                self._parse_date(vision_md.get("period_to")),
                self._parse_date(llm_md.get("period_to")),
                ent("period_to"),
            ),
            # Vision/LLM read the letterhead; the regex only matches generic titles
            issuing_authority=pick(
                vision_md.get("issuing_authority"),
                llm_md.get("issuing_authority"),
                ent("issuing_authority"),
            ),
            din=pick(ent("din"), vision_md.get("din"), llm_md.get("din")),
            officer_name=pick(vision_md.get("officer_name"), llm_md.get("officer_name")),
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
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    def to_api_response(self, report: AIReport) -> AiReportData:
        """Convert AIReport to API response format"""
        return report.to_ai_report_data()
