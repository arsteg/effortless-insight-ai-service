"""
Report generator stage for the pipeline
"""

import time
from datetime import date, datetime
from typing import Optional
from uuid import UUID
import structlog

from app.schemas.internal import PipelineContext
from app.schemas.report import AIReport, RiskAssessment, ConfidenceScores, VerificationResult, PreFilingChecklistItem
from app.schemas.responses import (
    AiReportData, NoticeMetadata, ActionItem, RequiredDocument, LegalReference
)
from app.services.scoring.risk_scorer import RiskScorer

logger = structlog.get_logger()


class ReportGenerator:
    """
    Stage 8: Report Generation

    Assembles all analysis results into the final report.
    """

    def __init__(self):
        self.risk_scorer = RiskScorer()

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

            # Build pre-filing checklist
            prefiling_checklist = self._build_prefiling_checklist(
                metadata=metadata,
                entities=entities,
                verification_result=verification_result,
                required_documents=required_documents,
            )

            # Calculate risk assessment with reasoning
            risk_assessment = None
            risk_factors = []
            if entities:
                notice_type = context.classification_output.notice_type if context.classification_output else None
                notice_category = context.classification_output.notice_category if context.classification_output else None
                risk_assessment = self.risk_scorer.calculate_risk(
                    entities=entities,
                    notice_type=notice_type,
                    notice_category=notice_category,
                )
                # Get simplified risk factors for display
                risk_factors = self.risk_scorer.get_risk_factors(
                    entities=entities,
                    notice_type=notice_type,
                )
                # Add reasoning from assessment if available
                if risk_assessment and risk_assessment.reasoning:
                    # Use reasoning if no simple factors available
                    if not risk_factors:
                        risk_factors = risk_assessment.reasoning

            # Assemble report
            report = AIReport(
                risk_score=risk_assessment.score if risk_assessment else (analysis.risk_score if analysis else 50),
                risk_level=risk_assessment.level if risk_assessment else (analysis.risk_level if analysis else "medium"),
                risk_assessment=risk_assessment,
                risk_factors=risk_factors,
                summary_en=analysis.summary_en if analysis else "",
                summary_hi=analysis.summary_hi if analysis else "",
                plain_english=analysis.plain_english if analysis else "",
                metadata=metadata,
                action_items=action_items,
                required_documents=required_documents,
                legal_references=legal_references,
                confidence_scores=confidence_scores,
                verification=verification_result,
                prefiling_checklist=prefiling_checklist,
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
            late_fee_amount=pick(ent("late_fee_amount"), vision_md.get("late_fee_amount"), llm_md.get("late_fee_amount")),
            cess_amount=pick(ent("cess_amount"), vision_md.get("cess_amount"), llm_md.get("cess_amount")),
            other_charges_amount=pick(ent("other_charges_amount"), vision_md.get("other_charges_amount"), llm_md.get("other_charges_amount")),
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

    def _build_prefiling_checklist(
        self,
        metadata: NoticeMetadata,
        entities,
        verification_result: Optional[VerificationResult],
        required_documents: list,
    ) -> list:
        """
        Build pre-filing review checklist

        Checks:
        1. Limitation period (is notice time-barred?)
        2. All required documents identified
        3. Calculation verification passed
        4. Response deadline status
        5. Appeal deadline computed
        6. Procedural compliance
        """
        checklist = []
        today = date.today()

        # 1. Limitation Period Check
        limitation_status = "unknown"
        limitation_details = (
            "Manual review required: issue date and tax period alone do not establish "
            "the applicable limitation deadline. Verify the provision, relevant dates "
            "and any applicable extensions before filing."
        )

        checklist.append(PreFilingChecklistItem(
            category="limitation",
            item="Limitation period verification",
            status=limitation_status,
            details=limitation_details,
            priority=1 if limitation_status == "warning" else 2,
        ))

        # 2. Required Documents Check
        if required_documents:
            mandatory_docs = [d for d in required_documents if d.mandatory]
            if mandatory_docs:
                checklist.append(PreFilingChecklistItem(
                    category="documents",
                    item=f"Collect {len(mandatory_docs)} mandatory documents",
                    status="warning",
                    details=", ".join([d.document for d in mandatory_docs[:5]]) +
                           (f" and {len(mandatory_docs) - 5} more" if len(mandatory_docs) > 5 else ""),
                    priority=1,
                ))
            optional_docs = [d for d in required_documents if not d.mandatory]
            if optional_docs:
                checklist.append(PreFilingChecklistItem(
                    category="documents",
                    item=f"{len(optional_docs)} optional supporting documents identified",
                    status="pass",
                    details=", ".join([d.document for d in optional_docs[:3]]) +
                           (f" and {len(optional_docs) - 3} more" if len(optional_docs) > 3 else ""),
                    priority=3,
                ))
        else:
            checklist.append(PreFilingChecklistItem(
                category="documents",
                item="No required documents identified",
                status="unknown",
                details="Review notice for document requirements",
                priority=2,
            ))

        # 3. Calculation Verification
        if verification_result:
            if verification_result.calculation_discrepancies:
                discrepancy_count = len(verification_result.calculation_discrepancies)
                errors = [d for d in verification_result.calculation_discrepancies if d.severity == "error"]
                if errors:
                    checklist.append(PreFilingChecklistItem(
                        category="calculations",
                        item="Calculation errors detected",
                        status="fail",
                        details=f"{len(errors)} calculation errors found that should be challenged",
                        priority=1,
                    ))
                else:
                    checklist.append(PreFilingChecklistItem(
                        category="calculations",
                        item="Minor calculation discrepancies",
                        status="warning",
                        details=f"{discrepancy_count} minor discrepancies - review before filing",
                        priority=2,
                    ))
            elif verification_result.amounts_verified:
                checklist.append(PreFilingChecklistItem(
                    category="calculations",
                    item="Demand calculations verified",
                    status="pass",
                    details="Tax, penalty and interest amounts are mathematically consistent",
                    priority=2,
                ))
        else:
            checklist.append(PreFilingChecklistItem(
                category="calculations",
                item="Calculations not verified",
                status="unknown",
                details="Manually verify demand amounts before responding",
                priority=2,
            ))

        # 4. Response Deadline Check
        if metadata.response_deadline:
            days_remaining = (metadata.response_deadline - today).days
            if days_remaining < 0:
                checklist.append(PreFilingChecklistItem(
                    category="deadlines",
                    item="Response deadline PASSED",
                    status="fail",
                    details=f"Deadline was {abs(days_remaining)} days ago. Request extension or file immediately.",
                    priority=1,
                ))
            elif days_remaining <= 3:
                checklist.append(PreFilingChecklistItem(
                    category="deadlines",
                    item="Response deadline URGENT",
                    status="warning",
                    details=f"Only {days_remaining} days remaining. Prioritize response.",
                    priority=1,
                ))
            elif days_remaining <= 7:
                checklist.append(PreFilingChecklistItem(
                    category="deadlines",
                    item="Response deadline approaching",
                    status="warning",
                    details=f"{days_remaining} days remaining until {metadata.response_deadline}",
                    priority=2,
                ))
            else:
                checklist.append(PreFilingChecklistItem(
                    category="deadlines",
                    item="Response deadline",
                    status="pass",
                    details=f"{days_remaining} days remaining until {metadata.response_deadline}",
                    priority=2,
                ))

        else:
            checklist.append(PreFilingChecklistItem(
                category="deadlines",
                item="Response deadline not identified",
                status="warning",
                details="Review notice to identify deadline or contact issuing authority",
                priority=1,
            ))

        checklist.append(PreFilingChecklistItem(
            category="deadlines",
            item="Appeal deadline verification",
            status="unknown",
            details="Cannot derive an appeal deadline from the notice response deadline. Review the applicable order and its communication date, if any.",
            priority=2,
        ))

        # 5. GSTIN Validation
        if verification_result and verification_result.gstin_valid:
            checklist.append(PreFilingChecklistItem(
                category="compliance",
                item="GSTIN verified",
                status="pass",
                details=f"GSTIN {metadata.gstin} is valid" if metadata.gstin else "GSTIN format validated",
                priority=3,
            ))
        elif metadata.gstin:
            checklist.append(PreFilingChecklistItem(
                category="compliance",
                item="GSTIN validation",
                status="unknown",
                details=f"Verify GSTIN {metadata.gstin} matches your records",
                priority=2,
            ))

        # 6. Section References Validation
        if verification_result:
            if verification_result.sections_valid:
                checklist.append(PreFilingChecklistItem(
                    category="procedural",
                    item="Legal sections verified",
                    status="pass",
                    details="Cited GST sections are valid",
                    priority=3,
                ))
            else:
                checklist.append(PreFilingChecklistItem(
                    category="procedural",
                    item="Check cited sections",
                    status="warning",
                    details="Some section references may be invalid - verify before responding",
                    priority=2,
                ))

        # 7. DIN Verification
        if metadata.din:
            checklist.append(PreFilingChecklistItem(
                category="procedural",
                item="DIN present",
                status="pass",
                details=f"Document Identification Number: {metadata.din}",
                priority=3,
            ))
        else:
            checklist.append(PreFilingChecklistItem(
                category="procedural",
                item="DIN not found",
                status="warning",
                details="CBIC DIN required for valid notices - verify authenticity",
                priority=2,
            ))

        # Sort by priority
        checklist.sort(key=lambda x: x.priority)

        return checklist
