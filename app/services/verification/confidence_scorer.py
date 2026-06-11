"""
Confidence scorer for AI analysis results
"""

from typing import Dict, Any, Optional
import structlog

from app.schemas.entities import ExtractedEntities
from app.schemas.report import ConfidenceScores

logger = structlog.get_logger()


class ConfidenceScorer:
    """
    Calculate confidence scores for different aspects of the analysis

    Scores consider:
    - OCR quality
    - Entity extraction success
    - LLM confidence
    - Verification results
    """

    def __init__(self):
        # Base confidence levels
        self.high_confidence_threshold = 85
        self.medium_confidence_threshold = 60
        self.low_confidence_threshold = 40

    def calculate_scores(
        self,
        ocr_confidence: float,
        entities: ExtractedEntities,
        llm_output: Dict[str, Any],
        verification_issues: int = 0,
        hallucinations: int = 0,
    ) -> ConfidenceScores:
        """
        Calculate confidence scores for all aspects

        Args:
            ocr_confidence: OCR provider confidence (0-1)
            entities: Extracted entities
            llm_output: LLM analysis output
            verification_issues: Number of verification issues found
            hallucinations: Number of potential hallucinations

        Returns:
            ConfidenceScores with individual and overall scores
        """
        # Convert OCR confidence to percentage
        base_ocr_confidence = int(ocr_confidence * 100)

        # Calculate individual scores
        notice_type_confidence = self._score_notice_type(entities, llm_output, base_ocr_confidence)
        deadline_confidence = self._score_deadline(entities, llm_output, base_ocr_confidence)
        amount_confidence = self._score_amount(entities, llm_output, base_ocr_confidence)
        gstin_confidence = self._score_gstin(entities, base_ocr_confidence)
        risk_confidence = self._score_risk_assessment(entities, llm_output, base_ocr_confidence)

        # Apply penalties for issues
        penalty = min(30, verification_issues * 5 + hallucinations * 10)

        # Calculate overall confidence
        overall = int((
            notice_type_confidence * 0.20 +
            deadline_confidence * 0.25 +
            amount_confidence * 0.20 +
            gstin_confidence * 0.15 +
            risk_confidence * 0.20
        ) - penalty)

        overall = max(0, min(100, overall))

        scores = ConfidenceScores(
            notice_type=notice_type_confidence,
            deadline=deadline_confidence,
            amount=amount_confidence,
            gstin=gstin_confidence,
            risk_assessment=risk_confidence,
            overall=overall,
        )

        logger.info(
            "Confidence scores calculated",
            overall=overall,
            notice_type=notice_type_confidence,
            deadline=deadline_confidence,
        )

        return scores

    def _score_notice_type(
        self,
        entities: ExtractedEntities,
        llm_output: Dict[str, Any],
        base_confidence: int
    ) -> int:
        """Score confidence in notice type classification"""
        score = base_confidence

        metadata = llm_output.get("metadata", {})
        notice_type = metadata.get("notice_type")
        notice_category = metadata.get("notice_category")

        # Higher confidence if notice type matches known patterns
        if notice_type:
            known_types = ["DRC", "ASMT", "REG", "RET", "GST", "ADT"]
            if any(notice_type.upper().startswith(t) for t in known_types):
                score = min(100, score + 10)
            else:
                score = max(40, score - 10)

        # Lower confidence if no type identified
        if not notice_type and not notice_category:
            score = max(30, score - 20)

        # Boost if category also present
        if notice_type and notice_category:
            score = min(100, score + 5)

        return score

    def _score_deadline(
        self,
        entities: ExtractedEntities,
        llm_output: Dict[str, Any],
        base_confidence: int
    ) -> int:
        """Score confidence in deadline extraction"""
        score = base_confidence

        # Check entity extraction
        has_entity_deadline = entities.response_deadline is not None

        # Check LLM output
        metadata = llm_output.get("metadata", {})
        has_llm_deadline = metadata.get("response_deadline") is not None

        if has_entity_deadline and has_llm_deadline:
            # Both found - high confidence
            score = min(100, score + 10)
        elif has_entity_deadline or has_llm_deadline:
            # Only one found - medium confidence
            score = max(50, score - 5)
        else:
            # None found - could be missing or notice doesn't have deadline
            score = max(40, score - 15)

        # Check date consistency
        if entities.issue_date and entities.response_deadline:
            if entities.issue_date <= entities.response_deadline:
                score = min(100, score + 5)
            else:
                score = max(30, score - 20)

        return score

    def _score_amount(
        self,
        entities: ExtractedEntities,
        llm_output: Dict[str, Any],
        base_confidence: int
    ) -> int:
        """Score confidence in amount extraction"""
        score = base_confidence

        # Check entity extraction
        has_amounts = (
            entities.tax_amount is not None or
            entities.penalty_amount is not None or
            entities.total_amount is not None
        )

        # Check LLM output
        metadata = llm_output.get("metadata", {})
        llm_has_amounts = (
            metadata.get("tax_amount") is not None or
            metadata.get("penalty_amount") is not None
        )

        if has_amounts and llm_has_amounts:
            score = min(100, score + 10)

            # Check if amounts match
            if entities.tax_amount and metadata.get("tax_amount"):
                if self._amounts_similar(entities.tax_amount, metadata["tax_amount"]):
                    score = min(100, score + 5)
                else:
                    score = max(40, score - 15)
        elif has_amounts or llm_has_amounts:
            score = max(50, score - 5)
        else:
            # No amounts - could be valid (informational notice)
            score = max(60, score - 5)

        return score

    def _score_gstin(
        self,
        entities: ExtractedEntities,
        base_confidence: int
    ) -> int:
        """Score confidence in GSTIN extraction"""
        score = base_confidence

        if not entities.primary_gstin:
            return max(30, score - 30)

        # Check if GSTIN is valid
        gstin_info = entities.get_primary_gstin_info()
        if gstin_info:
            if gstin_info.is_valid:
                score = min(100, score + 15)
            else:
                score = max(40, score - 20)
        else:
            score = max(50, score - 10)

        # Multiple GSTINs might indicate confusion
        if len(entities.gstins) > 2:
            score = max(50, score - 5)

        return score

    def _score_risk_assessment(
        self,
        entities: ExtractedEntities,
        llm_output: Dict[str, Any],
        base_confidence: int
    ) -> int:
        """Score confidence in risk assessment"""
        score = base_confidence

        # More data = higher confidence
        data_points = 0
        if entities.primary_gstin:
            data_points += 1
        if entities.response_deadline:
            data_points += 1
        if entities.tax_amount or entities.total_amount:
            data_points += 1
        if len(entities.sections) > 0:
            data_points += 1
        if llm_output.get("metadata", {}).get("notice_type"):
            data_points += 1

        # Adjust score based on data availability
        if data_points >= 4:
            score = min(100, score + 10)
        elif data_points >= 2:
            score = min(100, score + 5)
        else:
            score = max(50, score - 10)

        return score

    def _amounts_similar(self, amount1: float, amount2: float, tolerance: float = 0.01) -> bool:
        """Check if two amounts are similar within tolerance"""
        if amount1 == 0 and amount2 == 0:
            return True

        max_amt = max(abs(amount1), abs(amount2))
        diff = abs(amount1 - amount2)

        return diff / max_amt <= tolerance

    def get_confidence_level(self, score: int) -> str:
        """Convert score to confidence level string"""
        if score >= self.high_confidence_threshold:
            return "high"
        elif score >= self.medium_confidence_threshold:
            return "medium"
        elif score >= self.low_confidence_threshold:
            return "low"
        else:
            return "very_low"
