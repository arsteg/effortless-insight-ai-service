"""
Unit tests for risk scorer
"""

import pytest
from datetime import date, timedelta

from app.services.scoring.risk_scorer import RiskScorer
from app.schemas.entities import ExtractedEntities


class TestRiskScorer:
    """Test cases for risk scoring"""

    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    @pytest.fixture
    def base_entities(self):
        return ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
        )

    def test_score_range(self, scorer, base_entities):
        """Test that scores are within valid range"""
        result = scorer.calculate_risk(base_entities)

        assert 0 <= result.score <= 100

    def test_risk_level_low(self, scorer, base_entities):
        """Test low risk level"""
        result = scorer.calculate_risk(base_entities)

        if result.score < 25:
            assert result.level == "low"

    def test_risk_level_critical(self, scorer, base_entities):
        """Test critical risk for high amounts and urgent deadline"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            tax_amount=15_00_000,  # 15 lakhs
            response_deadline=date.today() + timedelta(days=2),
        )

        result = scorer.calculate_risk(
            entities,
            notice_type="DRC-07",
            notice_category="demand"
        )

        assert result.score >= 70
        assert result.level in ["high", "critical"]

    def test_category_scoring_drc01(self, scorer, base_entities):
        """Test DRC-01 notice scoring"""
        result = scorer.calculate_risk(
            base_entities,
            notice_type="DRC-01"
        )

        # DRC-01 is a high-risk notice type
        assert result.notice_category_score >= 80

    def test_category_scoring_asmt10(self, scorer, base_entities):
        """Test ASMT-10 notice scoring"""
        result = scorer.calculate_risk(
            base_entities,
            notice_type="ASMT-10"
        )

        assert result.notice_category_score >= 70

    def test_amount_scoring_high(self, scorer, base_entities):
        """Test high amount scoring"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            tax_amount=50_00_000,  # 50 lakhs
        )

        result = scorer.calculate_risk(entities)

        assert result.tax_amount_score >= 80

    def test_amount_scoring_low(self, scorer, base_entities):
        """Test low amount scoring"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            tax_amount=10_000,  # 10K
        )

        result = scorer.calculate_risk(entities)

        assert result.tax_amount_score <= 40

    def test_deadline_scoring_overdue(self, scorer, base_entities):
        """Test overdue deadline scoring"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            response_deadline=date.today() - timedelta(days=5),
        )

        result = scorer.calculate_risk(entities)

        assert result.deadline_urgency_score == 100

    def test_deadline_scoring_urgent(self, scorer, base_entities):
        """Test urgent deadline scoring"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            response_deadline=date.today() + timedelta(days=3),
        )

        result = scorer.calculate_risk(entities)

        assert result.deadline_urgency_score >= 90

    def test_deadline_scoring_comfortable(self, scorer, base_entities):
        """Test comfortable deadline scoring"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            response_deadline=date.today() + timedelta(days=45),
        )

        result = scorer.calculate_risk(entities)

        assert result.deadline_urgency_score <= 30

    def test_prior_history_scoring(self, scorer, base_entities):
        """Test prior history scoring"""
        result_no_history = scorer.calculate_risk(base_entities, prior_notices=0)
        result_high_history = scorer.calculate_risk(base_entities, prior_notices=6)

        assert result_high_history.prior_history_score > result_no_history.prior_history_score

    def test_get_risk_factors(self, scorer, base_entities):
        """Test risk factor explanation"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            tax_amount=10_00_000,
            response_deadline=date.today() + timedelta(days=5),
        )

        factors = scorer.get_risk_factors(entities, "DRC-01")

        assert len(factors) > 0
        assert any("deadline" in f.lower() or "amount" in f.lower() for f in factors)

    def test_weighted_calculation(self, scorer, base_entities):
        """Test that weights sum to 1.0"""
        total_weight = sum(scorer.WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.01
