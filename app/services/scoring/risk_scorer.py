"""
Risk scoring service for GST notices
"""

from datetime import date, timedelta
from typing import Optional, Dict
import structlog

from app.schemas.entities import ExtractedEntities
from app.schemas.report import RiskAssessment

logger = structlog.get_logger()


# Notice category risk scores (0-100)
CATEGORY_RISK_SCORES = {
    # Critical - Demand and Recovery
    "DRC-01": 85,  # Show Cause Notice
    "DRC-07": 90,  # Demand Order
    "DRC-13": 80,  # Recovery Notice

    # High - Assessment
    "ASMT-10": 75,  # Show Cause for Scrutiny
    "ASMT-12": 70,  # Scrutiny Order
    "ASMT-14": 65,  # Show Cause for Best Judgment

    # Medium-High - Registration
    "REG-17": 60,  # Show Cause for Cancellation
    "REG-19": 55,  # Order of Cancellation

    # Medium - Audit
    "ADT-01": 50,  # Audit Intimation
    "ADT-02": 55,  # Audit Report

    # Medium-Low - Returns
    "RET-01": 40,  # Return Default Notice
    "GSTR-3A": 45,  # Non-filing Notice

    # Low - Informational
    "REG-03": 25,  # Registration Clarification
    "REG-06": 20,  # Registration Certificate
}

# Default scores for unknown categories
DEFAULT_CATEGORY_SCORES = {
    "demand": 85,
    "assessment": 70,
    "registration": 50,
    "audit": 55,
    "refund": 30,
    "returns": 40,
    "other": 50,
}


class RiskScorer:
    """
    Calculate risk score for GST notices

    Score Weights:
    - Notice Category: 25%
    - Tax Amount: 20%
    - Deadline Urgency: 20%
    - Penalty Potential: 15%
    - Prior History: 10%
    - Complexity: 10%

    Score Range: 0-100
    Levels: low (0-24), medium (25-49), high (50-74), critical (75-100)
    """

    # Weight configuration
    WEIGHTS = {
        "notice_category": 0.25,
        "tax_amount": 0.20,
        "deadline_urgency": 0.20,
        "penalty_potential": 0.15,
        "prior_history": 0.10,
        "complexity": 0.10,
    }

    # Amount thresholds (in INR)
    AMOUNT_THRESHOLDS = {
        "critical": 10_00_000,  # 10 Lakhs
        "high": 5_00_000,      # 5 Lakhs
        "medium": 1_00_000,    # 1 Lakh
        "low": 25_000,         # 25K
    }

    # Deadline thresholds (in days)
    DEADLINE_THRESHOLDS = {
        "critical": 3,
        "high": 7,
        "medium": 15,
        "low": 30,
    }

    def calculate_risk(
        self,
        entities: ExtractedEntities,
        notice_type: Optional[str] = None,
        notice_category: Optional[str] = None,
        prior_notices: int = 0,
        complexity_indicators: Optional[Dict[str, bool]] = None,
    ) -> RiskAssessment:
        """
        Calculate comprehensive risk score

        Args:
            entities: Extracted entities from the notice
            notice_type: Type of notice (DRC-01, ASMT-10, etc.)
            notice_category: Category (demand, assessment, etc.)
            prior_notices: Number of prior notices for this GSTIN
            complexity_indicators: Dict of complexity factors

        Returns:
            RiskAssessment with score and breakdown
        """
        logger.info("Calculating risk score", notice_type=notice_type)

        # Calculate component scores
        category_score = self._score_category(notice_type, notice_category)
        amount_score = self._score_amount(entities)
        deadline_score = self._score_deadline(entities)
        penalty_score = self._score_penalty_potential(entities, notice_type)
        history_score = self._score_prior_history(prior_notices)
        complexity_score = self._score_complexity(entities, complexity_indicators)

        # Calculate weighted total
        total_score = int(
            category_score * self.WEIGHTS["notice_category"] +
            amount_score * self.WEIGHTS["tax_amount"] +
            deadline_score * self.WEIGHTS["deadline_urgency"] +
            penalty_score * self.WEIGHTS["penalty_potential"] +
            history_score * self.WEIGHTS["prior_history"] +
            complexity_score * self.WEIGHTS["complexity"]
        )

        # Ensure score is in valid range
        total_score = max(0, min(100, total_score))

        # Determine risk level
        risk_level = self._score_to_level(total_score)

        logger.info(
            "Risk score calculated",
            score=total_score,
            level=risk_level,
            category=category_score,
            amount=amount_score,
            deadline=deadline_score,
        )

        return RiskAssessment(
            score=total_score,
            level=risk_level,
            notice_category_score=category_score,
            tax_amount_score=amount_score,
            deadline_urgency_score=deadline_score,
            penalty_potential_score=penalty_score,
            prior_history_score=history_score,
            complexity_score=complexity_score,
            weights=self.WEIGHTS,
        )

    def _score_category(
        self,
        notice_type: Optional[str],
        notice_category: Optional[str]
    ) -> int:
        """Score based on notice category/type"""
        if notice_type:
            # Normalize notice type
            normalized = notice_type.upper().replace(" ", "").replace("-", "-")

            # Try exact match
            if normalized in CATEGORY_RISK_SCORES:
                return CATEGORY_RISK_SCORES[normalized]

            # Try without hyphen
            normalized_no_hyphen = normalized.replace("-", "")
            for key, score in CATEGORY_RISK_SCORES.items():
                if key.replace("-", "") == normalized_no_hyphen:
                    return score

        # Fall back to category
        if notice_category:
            category_lower = notice_category.lower()
            return DEFAULT_CATEGORY_SCORES.get(category_lower, 50)

        return 50  # Default medium risk

    def _score_amount(self, entities: ExtractedEntities) -> int:
        """Score based on tax/demand amount"""
        # Use total amount if available, else tax amount
        amount = entities.total_amount or entities.tax_amount

        if amount is None:
            return 30  # Unknown amount = medium-low risk

        if amount >= self.AMOUNT_THRESHOLDS["critical"]:
            return 100
        elif amount >= self.AMOUNT_THRESHOLDS["high"]:
            return 80
        elif amount >= self.AMOUNT_THRESHOLDS["medium"]:
            return 60
        elif amount >= self.AMOUNT_THRESHOLDS["low"]:
            return 40
        else:
            return 20

    def _score_deadline(self, entities: ExtractedEntities) -> int:
        """Score based on deadline urgency"""
        deadline = entities.response_deadline

        if deadline is None:
            return 50  # Unknown deadline = medium risk

        days_remaining = (deadline - date.today()).days

        if days_remaining < 0:
            return 100  # Overdue!
        elif days_remaining <= self.DEADLINE_THRESHOLDS["critical"]:
            return 95
        elif days_remaining <= self.DEADLINE_THRESHOLDS["high"]:
            return 80
        elif days_remaining <= self.DEADLINE_THRESHOLDS["medium"]:
            return 60
        elif days_remaining <= self.DEADLINE_THRESHOLDS["low"]:
            return 40
        else:
            return 20

    def _score_penalty_potential(
        self,
        entities: ExtractedEntities,
        notice_type: Optional[str]
    ) -> int:
        """Score based on penalty potential"""
        score = 0

        # If penalty already mentioned, high risk
        if entities.penalty_amount and entities.penalty_amount > 0:
            score = 80

            # Higher penalty = higher risk
            if entities.penalty_amount >= 1_00_000:
                score = 100
            elif entities.penalty_amount >= 50_000:
                score = 90

        # Notice types with high penalty risk
        high_penalty_types = ["DRC-01", "DRC-07", "ASMT-10", "ASMT-14"]
        if notice_type and any(t in notice_type.upper() for t in high_penalty_types):
            score = max(score, 70)

        # Interest mentioned
        if entities.interest_amount and entities.interest_amount > 0:
            score = max(score, 60)

        return score if score > 0 else 30

    def _score_prior_history(self, prior_notices: int) -> int:
        """Score based on prior notice history"""
        if prior_notices == 0:
            return 10
        elif prior_notices == 1:
            return 30
        elif prior_notices <= 3:
            return 50
        elif prior_notices <= 5:
            return 70
        else:
            return 90

    def _score_complexity(
        self,
        entities: ExtractedEntities,
        indicators: Optional[Dict[str, bool]]
    ) -> int:
        """Score based on notice complexity"""
        score = 30  # Base complexity

        # More sections = more complex
        if len(entities.sections) > 5:
            score += 30
        elif len(entities.sections) > 2:
            score += 15

        # Multiple GSTINs
        if len(entities.gstins) > 1:
            score += 10

        # Long tax period
        if entities.period_from and entities.period_to:
            period_days = (entities.period_to - entities.period_from).days
            if period_days > 365:
                score += 20
            elif period_days > 180:
                score += 10

        # Additional indicators
        if indicators:
            if indicators.get("multiple_tax_heads"):
                score += 15
            if indicators.get("cross_border"):
                score += 20
            if indicators.get("fraud_allegation"):
                score += 30
            if indicators.get("prosecution_risk"):
                score += 25

        return min(100, score)

    def _score_to_level(self, score: int) -> str:
        """Convert score to risk level"""
        if score < 25:
            return "low"
        elif score < 50:
            return "medium"
        elif score < 75:
            return "high"
        else:
            return "critical"

    def get_risk_factors(
        self,
        entities: ExtractedEntities,
        notice_type: Optional[str] = None,
    ) -> list:
        """
        Get list of risk factors for explanation

        Returns list of factor descriptions
        """
        factors = []

        # Check deadline
        if entities.response_deadline:
            days = (entities.response_deadline - date.today()).days
            if days < 0:
                factors.append(f"CRITICAL: Deadline has passed ({abs(days)} days overdue)")
            elif days <= 3:
                factors.append(f"URGENT: Only {days} days until deadline")
            elif days <= 7:
                factors.append(f"High urgency: {days} days until deadline")

        # Check amount
        total = entities.total_amount or entities.tax_amount
        if total:
            if total >= self.AMOUNT_THRESHOLDS["critical"]:
                factors.append(f"Large demand amount: ₹{total:,.2f}")
            elif total >= self.AMOUNT_THRESHOLDS["high"]:
                factors.append(f"Significant amount involved: ₹{total:,.2f}")

        # Check penalty
        if entities.penalty_amount and entities.penalty_amount > 0:
            factors.append(f"Penalty of ₹{entities.penalty_amount:,.2f} mentioned")

        # Check notice type
        if notice_type:
            nt = notice_type.upper()
            if "DRC-01" in nt:
                factors.append("Show Cause Notice - requires detailed response")
            elif "DRC-07" in nt:
                factors.append("Demand Order - payment or appeal required")
            elif "ASMT" in nt:
                factors.append("Assessment/Scrutiny - records review needed")

        return factors
