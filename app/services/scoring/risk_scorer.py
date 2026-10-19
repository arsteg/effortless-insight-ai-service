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
            RiskAssessment with score, breakdown, and reasoning
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

        # Generate detailed reasoning
        reasoning = self._generate_reasoning(
            entities=entities,
            notice_type=notice_type,
            notice_category=notice_category,
            prior_notices=prior_notices,
            complexity_indicators=complexity_indicators,
            category_score=category_score,
            amount_score=amount_score,
            deadline_score=deadline_score,
            penalty_score=penalty_score,
            history_score=history_score,
            complexity_score=complexity_score,
            total_score=total_score,
            risk_level=risk_level,
        )

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
            reasoning=reasoning,
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

    def _generate_reasoning(
        self,
        entities: ExtractedEntities,
        notice_type: Optional[str],
        notice_category: Optional[str],
        prior_notices: int,
        complexity_indicators: Optional[Dict[str, bool]],
        category_score: int,
        amount_score: int,
        deadline_score: int,
        penalty_score: int,
        history_score: int,
        complexity_score: int,
        total_score: int,
        risk_level: str,
    ) -> list:
        """
        Generate detailed reasoning for the risk classification.

        Returns a list of human-readable reasons explaining the risk level.
        """
        reasons = []

        # Notice type reasoning
        if notice_type:
            nt = notice_type.upper()
            if "DRC-01" in nt:
                reasons.append(
                    f"Notice type DRC-01 (Show Cause Notice) requires a detailed response "
                    f"and carries significant compliance implications (category score: {category_score}/100)"
                )
            elif "DRC-07" in nt:
                reasons.append(
                    f"Notice type DRC-07 (Demand Order) is a final order requiring immediate "
                    f"payment or appeal (category score: {category_score}/100)"
                )
            elif "DRC-13" in nt:
                reasons.append(
                    f"Notice type DRC-13 (Recovery Notice) indicates active recovery proceedings "
                    f"(category score: {category_score}/100)"
                )
            elif "ASMT-10" in nt:
                reasons.append(
                    f"Notice type ASMT-10 (Scrutiny Notice) requires document submission and "
                    f"explanation of discrepancies (category score: {category_score}/100)"
                )
            elif "ASMT-14" in nt:
                reasons.append(
                    f"Notice type ASMT-14 (Best Judgment Assessment) carries high risk as it "
                    f"may result in tax demand without adequate representation (category score: {category_score}/100)"
                )
            elif "REG-17" in nt or "REG-19" in nt:
                reasons.append(
                    f"Registration cancellation notice threatens business continuity "
                    f"(category score: {category_score}/100)"
                )
            elif "ADT" in nt:
                reasons.append(
                    f"Audit notice requires comprehensive record keeping and compliance review "
                    f"(category score: {category_score}/100)"
                )
            elif category_score >= 70:
                reasons.append(
                    f"Notice type '{notice_type}' carries elevated compliance requirements "
                    f"(category score: {category_score}/100)"
                )
        elif notice_category and category_score >= 50:
            reasons.append(
                f"Notice category '{notice_category}' indicates {self._get_category_description(notice_category)} "
                f"(category score: {category_score}/100)"
            )

        # Deadline reasoning
        if entities.response_deadline:
            days = (entities.response_deadline - date.today()).days
            if days < 0:
                reasons.append(
                    f"CRITICAL: Response deadline has passed ({abs(days)} days overdue). "
                    f"Immediate action required to avoid penalties (deadline urgency: {deadline_score}/100)"
                )
            elif days <= 3:
                reasons.append(
                    f"URGENT: Only {days} days remaining until deadline. "
                    f"Prioritize immediate response preparation (deadline urgency: {deadline_score}/100)"
                )
            elif days <= 7:
                reasons.append(
                    f"High urgency: {days} days until response deadline. "
                    f"Recommend starting response preparation now (deadline urgency: {deadline_score}/100)"
                )
            elif days <= 15:
                reasons.append(
                    f"Moderate urgency: {days} days until deadline "
                    f"(deadline urgency: {deadline_score}/100)"
                )
        elif deadline_score >= 50:
            reasons.append(
                f"Response deadline not clearly identified - recommend verifying deadline "
                f"from original notice (deadline urgency: {deadline_score}/100)"
            )

        # Amount reasoning
        total = entities.total_amount or entities.tax_amount
        if total:
            if total >= self.AMOUNT_THRESHOLDS["critical"]:
                reasons.append(
                    f"Large demand amount of ₹{total:,.2f} significantly increases financial exposure "
                    f"(amount score: {amount_score}/100)"
                )
            elif total >= self.AMOUNT_THRESHOLDS["high"]:
                reasons.append(
                    f"Substantial demand amount of ₹{total:,.2f} warrants careful review "
                    f"(amount score: {amount_score}/100)"
                )
            elif total >= self.AMOUNT_THRESHOLDS["medium"]:
                reasons.append(
                    f"Demand amount of ₹{total:,.2f} requires attention "
                    f"(amount score: {amount_score}/100)"
                )
        elif amount_score >= 30:
            reasons.append(
                f"Tax/demand amount not clearly extracted - verify from original notice "
                f"(amount score: {amount_score}/100)"
            )

        # Penalty reasoning
        if entities.penalty_amount and entities.penalty_amount > 0:
            reasons.append(
                f"Penalty of ₹{entities.penalty_amount:,.2f} already mentioned in notice "
                f"(penalty potential: {penalty_score}/100)"
            )
        elif penalty_score >= 70:
            reasons.append(
                f"Notice type carries high potential for penalty imposition "
                f"(penalty potential: {penalty_score}/100)"
            )

        # Interest reasoning
        if entities.interest_amount and entities.interest_amount > 0:
            reasons.append(
                f"Interest of ₹{entities.interest_amount:,.2f} accruing on unpaid amount"
            )

        # Prior history reasoning
        if prior_notices > 0:
            if prior_notices >= 5:
                reasons.append(
                    f"Multiple prior notices ({prior_notices}) for this GSTIN indicate "
                    f"pattern of compliance issues (history score: {history_score}/100)"
                )
            elif prior_notices >= 2:
                reasons.append(
                    f"Prior notices ({prior_notices}) exist for this GSTIN - "
                    f"consider systemic review (history score: {history_score}/100)"
                )

        # Complexity reasoning
        if complexity_indicators:
            complexity_factors = []
            if complexity_indicators.get("fraud_allegation"):
                complexity_factors.append("fraud allegation")
            if complexity_indicators.get("prosecution_risk"):
                complexity_factors.append("prosecution risk")
            if complexity_indicators.get("cross_border"):
                complexity_factors.append("cross-border transactions")
            if complexity_indicators.get("multiple_tax_heads"):
                complexity_factors.append("multiple tax heads")

            if complexity_factors:
                reasons.append(
                    f"Complexity factors present: {', '.join(complexity_factors)} "
                    f"(complexity score: {complexity_score}/100)"
                )

        if len(entities.sections) > 5:
            reasons.append(
                f"Multiple legal sections ({len(entities.sections)}) cited indicate "
                f"complex legal issues requiring expert review"
            )

        # Tax period reasoning
        if entities.period_from and entities.period_to:
            period_days = (entities.period_to - entities.period_from).days
            if period_days > 365:
                years = period_days // 365
                reasons.append(
                    f"Extended tax period of {years}+ years may involve substantial "
                    f"accumulated liability and documentation requirements"
                )

        # Summary reasoning
        if not reasons:
            if risk_level == "low":
                reasons.append("Standard compliance notice with manageable requirements")
            elif risk_level == "medium":
                reasons.append("Notice requires attention but presents moderate risk")
            elif risk_level == "high":
                reasons.append("Notice presents significant compliance and financial risk")
            else:
                reasons.append("Critical notice requiring immediate professional attention")

        return reasons

    def _get_category_description(self, category: str) -> str:
        """Get human-readable description for notice category"""
        descriptions = {
            "demand": "tax demand requiring payment or response",
            "assessment": "assessment proceedings requiring document submission",
            "registration": "registration-related compliance requirements",
            "audit": "audit proceedings requiring record review",
            "refund": "refund processing matter",
            "returns": "return filing compliance issue",
        }
        return descriptions.get(category.lower(), "compliance requirements")

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
