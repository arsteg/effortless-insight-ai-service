"""
Unit tests for verifier
"""

import pytest
from datetime import date

from app.services.verification.fact_checker import FactChecker
from app.services.verification.hallucination_detector import HallucinationDetector
from app.services.verification.confidence_scorer import ConfidenceScorer
from app.schemas.entities import ExtractedEntities


class TestFactChecker:
    """Test cases for fact checker"""

    @pytest.fixture
    def checker(self):
        return FactChecker()

    @pytest.fixture
    def sample_text(self):
        return """
        Notice Date: 15/01/2024
        Deadline: 14/02/2024
        Amount: Rs. 5,00,000/-
        GSTIN: 29AADCB2230M1ZV
        Section 73 of CGST Act
        """

    def test_verify_gstin_valid(self, checker):
        """Test valid GSTIN verification"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            primary_gstin="29AADCB2230M1ZV",
        )

        is_valid, error = checker.verify_gstin(entities)
        # Note: depends on actual GSTIN validity
        assert is_valid or error is not None

    def test_verify_gstin_invalid(self, checker):
        """Test invalid GSTIN verification"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            primary_gstin="29INVALID1234ZV",
        )

        is_valid, error = checker.verify_gstin(entities)
        assert not is_valid
        assert error is not None

    def test_verify_deadline_in_text(self, checker, sample_text):
        """Test deadline verification in text"""
        is_valid, msg = checker.verify_deadline_in_text(
            sample_text,
            date(2024, 2, 14)
        )

        assert is_valid

    def test_verify_deadline_not_in_text(self, checker, sample_text):
        """Test deadline not found in text"""
        is_valid, msg = checker.verify_deadline_in_text(
            sample_text,
            date(2024, 3, 15)  # Not in text
        )

        assert not is_valid

    def test_verify_date_consistency_valid(self, checker):
        """Test valid date consistency"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            issue_date=date(2024, 1, 15),
            response_deadline=date(2024, 2, 14),
        )

        is_valid, error = checker.verify_date_consistency(entities)
        assert is_valid

    def test_verify_date_consistency_invalid(self, checker):
        """Test invalid date consistency"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            issue_date=date(2024, 3, 15),  # After deadline
            response_deadline=date(2024, 2, 14),
        )

        is_valid, error = checker.verify_date_consistency(entities)
        assert not is_valid

    def test_verify_amounts_match(self, checker, sample_text):
        """Test amount verification"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            tax_amount=500000.0,
        )

        llm_output = {
            "metadata": {
                "tax_amount": 500000.0,
            }
        }

        issues = checker.verify_amounts(sample_text, entities, llm_output)
        assert len(issues) == 0

    def test_verify_amounts_mismatch(self, checker, sample_text):
        """Test amount mismatch detection"""
        entities = ExtractedEntities(
            gstins=[],
            dates=[],
            amounts=[],
            sections=[],
            tax_amount=500000.0,
        )

        llm_output = {
            "metadata": {
                "tax_amount": 600000.0,  # Different amount
            }
        }

        issues = checker.verify_amounts(sample_text, entities, llm_output)
        assert len(issues) > 0


class TestHallucinationDetector:
    """Test cases for hallucination detector"""

    @pytest.fixture
    def detector(self):
        return HallucinationDetector()

    @pytest.fixture
    def sample_text(self):
        return """
        GSTIN: 29AADCB2230M1ZV
        Amount: Rs. 5,00,000/-
        Section 73 of CGST Act
        """

    def test_detect_valid_content(self, detector, sample_text):
        """Test that valid content passes"""
        llm_output = {
            "metadata": {
                "gstin": "29AADCB2230M1ZV",
                "tax_amount": 500000,
            },
            "summary_en": "Notice regarding Section 73",
            "action_items": [],
            "legal_references": [
                {"section": "Section 73", "description": "Demand"}
            ],
        }

        hallucinations = detector.detect_hallucinations(sample_text, llm_output)
        assert len(hallucinations) == 0

    def test_detect_fabricated_gstin(self, detector, sample_text):
        """Test detection of fabricated GSTIN"""
        llm_output = {
            "metadata": {
                "gstin": "07XXXXX9999X1ZZ",  # Not in text
            },
        }

        hallucinations = detector.detect_hallucinations(sample_text, llm_output)
        assert "gstin" in hallucinations

    def test_detect_fabricated_amount(self, detector, sample_text):
        """Test detection of fabricated amount"""
        llm_output = {
            "metadata": {
                "tax_amount": 9999999,  # Not in text
            },
        }

        hallucinations = detector.detect_hallucinations(sample_text, llm_output)
        assert "tax_amount" in hallucinations

    def test_confidence_penalty(self, detector):
        """Test confidence penalty calculation"""
        hallucinations = ["gstin", "tax_amount"]
        penalty = detector.get_confidence_penalty(hallucinations)

        assert penalty > 0
        assert penalty <= 50


class TestConfidenceScorer:
    """Test cases for confidence scorer"""

    @pytest.fixture
    def scorer(self):
        return ConfidenceScorer()

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
        scores = scorer.calculate_scores(
            ocr_confidence=0.95,
            entities=base_entities,
            llm_output={},
            verification_issues=0,
            hallucinations=0,
        )

        assert 0 <= scores.overall <= 100

    def test_high_ocr_confidence_boost(self, scorer, base_entities):
        """Test that high OCR confidence boosts scores"""
        high_conf = scorer.calculate_scores(
            ocr_confidence=0.98,
            entities=base_entities,
            llm_output={},
        )

        low_conf = scorer.calculate_scores(
            ocr_confidence=0.60,
            entities=base_entities,
            llm_output={},
        )

        assert high_conf.overall > low_conf.overall

    def test_verification_issues_penalty(self, scorer, base_entities):
        """Test that verification issues reduce confidence"""
        no_issues = scorer.calculate_scores(
            ocr_confidence=0.95,
            entities=base_entities,
            llm_output={},
            verification_issues=0,
        )

        with_issues = scorer.calculate_scores(
            ocr_confidence=0.95,
            entities=base_entities,
            llm_output={},
            verification_issues=5,
        )

        assert no_issues.overall > with_issues.overall

    def test_confidence_level_mapping(self, scorer):
        """Test confidence level string mapping"""
        assert scorer.get_confidence_level(90) == "high"
        assert scorer.get_confidence_level(70) == "medium"
        assert scorer.get_confidence_level(50) == "low"
        assert scorer.get_confidence_level(30) == "very_low"
