"""
Main verifier service combining all verification components
"""

from typing import Dict, Any, List, Tuple
import structlog

from app.schemas.entities import ExtractedEntities
from app.schemas.report import VerificationResult, ConfidenceScores
from app.schemas.internal import VerificationOutput
from app.services.verification.fact_checker import FactChecker
from app.services.verification.hallucination_detector import HallucinationDetector
from app.services.verification.confidence_scorer import ConfidenceScorer

logger = structlog.get_logger()


class Verifier:
    """
    Main verifier service that orchestrates all verification checks

    Combines:
    - Fact checking
    - Hallucination detection
    - Confidence scoring
    """

    def __init__(self):
        self.fact_checker = FactChecker()
        self.hallucination_detector = HallucinationDetector()
        self.confidence_scorer = ConfidenceScorer()

    async def verify(
        self,
        original_text: str,
        entities: ExtractedEntities,
        llm_output: Dict[str, Any],
        ocr_confidence: float = 0.95,
    ) -> VerificationOutput:
        """
        Run full verification pipeline

        Args:
            original_text: Original OCR text
            entities: Extracted entities
            llm_output: LLM analysis output
            ocr_confidence: OCR provider confidence

        Returns:
            VerificationOutput with all results
        """
        logger.info("Starting verification pipeline")

        # 1. Run fact checking
        facts_valid, issues, warnings = self.fact_checker.verify_all(
            original_text, entities, llm_output
        )

        # 2. Detect hallucinations
        hallucinations = self.hallucination_detector.detect_hallucinations(
            original_text, llm_output
        )

        # 3. Build verification result
        verification = VerificationResult(
            is_verified=facts_valid and len(hallucinations) == 0,
            issues=issues,
            warnings=warnings,
            potential_hallucinations=hallucinations,
            deadline_verified=not any("deadline" in i.lower() for i in warnings),
            amounts_verified=not any("amount" in i.lower() for i in issues),
            sections_valid=not any("section" in i.lower() or "rule" in i.lower() for i in warnings),
            gstin_valid=not any("gstin" in i.lower() for i in issues),
            dates_consistent=not any("date" in i.lower() for i in issues),
        )

        # 4. Make adjustments if needed
        adjustments = self._make_adjustments(llm_output, issues, hallucinations)

        logger.info(
            "Verification complete",
            verified=verification.is_verified,
            issues=len(issues),
            warnings=len(warnings),
            hallucinations=len(hallucinations),
            adjustments=len(adjustments)
        )

        return VerificationOutput(
            success=True,
            verification=verification,
            adjustments_made=adjustments,
        )

    def calculate_confidence(
        self,
        ocr_confidence: float,
        entities: ExtractedEntities,
        llm_output: Dict[str, Any],
        verification_output: VerificationOutput,
    ) -> ConfidenceScores:
        """
        Calculate confidence scores based on verification results

        Args:
            ocr_confidence: OCR provider confidence
            entities: Extracted entities
            llm_output: LLM analysis output
            verification_output: Verification results

        Returns:
            ConfidenceScores
        """
        verification_issues = len(verification_output.verification.issues)
        hallucinations = len(verification_output.verification.potential_hallucinations)

        return self.confidence_scorer.calculate_scores(
            ocr_confidence=ocr_confidence,
            entities=entities,
            llm_output=llm_output,
            verification_issues=verification_issues,
            hallucinations=hallucinations,
        )

    def _make_adjustments(
        self,
        llm_output: Dict[str, Any],
        issues: List[str],
        hallucinations: List[str],
    ) -> List[str]:
        """
        Make adjustments to LLM output based on verification

        Returns list of adjustments made
        """
        adjustments = []

        # Adjust confidence scores based on issues
        if issues or hallucinations:
            current_confidence = llm_output.get("confidence_scores", {})
            if current_confidence:
                # Apply penalty
                penalty = self.hallucination_detector.get_confidence_penalty(hallucinations)
                penalty += len(issues) * 5

                for key in current_confidence:
                    if isinstance(current_confidence[key], (int, float)):
                        original = current_confidence[key]
                        current_confidence[key] = max(0, current_confidence[key] - penalty)
                        if original != current_confidence[key]:
                            adjustments.append(f"Reduced {key} confidence by {penalty}")

        # Remove potentially hallucinated action items
        if "action_items" in hallucinations:
            # Don't remove, just mark
            adjustments.append("Action items may contain unverified information")

        return adjustments

    async def quick_verify(
        self,
        original_text: str,
        entities: ExtractedEntities,
    ) -> Tuple[bool, List[str]]:
        """
        Quick verification of just extracted entities

        Returns:
            Tuple of (is_valid, issues)
        """
        issues = []

        # Verify GSTIN
        gstin_valid, gstin_issue = self.fact_checker.verify_gstin(entities)
        if not gstin_valid and gstin_issue:
            issues.append(gstin_issue)

        # Verify date consistency
        date_valid, date_issue = self.fact_checker.verify_date_consistency(entities)
        if not date_valid and date_issue:
            issues.append(date_issue)

        # Verify deadline in text
        if entities.response_deadline:
            deadline_valid, deadline_msg = self.fact_checker.verify_deadline_in_text(
                original_text, entities.response_deadline
            )
            if not deadline_valid and deadline_msg:
                issues.append(deadline_msg)

        return len(issues) == 0, issues

    def get_verification_summary(
        self,
        verification: VerificationResult
    ) -> str:
        """
        Get a human-readable verification summary

        Returns:
            Summary string
        """
        if verification.is_verified:
            if verification.warnings:
                return f"Verified with {len(verification.warnings)} warning(s)"
            return "Fully verified"

        if verification.issues:
            return f"Verification failed: {len(verification.issues)} issue(s) found"

        if verification.potential_hallucinations:
            return f"Potential inaccuracies in {len(verification.potential_hallucinations)} field(s)"

        return "Verification incomplete"
