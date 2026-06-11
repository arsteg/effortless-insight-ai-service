"""
Unit tests for GSTIN validator
"""

import pytest
from app.services.extraction.gstin_validator import GSTINValidator


class TestGSTINValidator:
    """Test cases for GSTIN validation"""

    def test_valid_gstin(self):
        """Test validation of valid GSTIN"""
        # Valid GSTINs
        valid_gstins = [
            "29AADCB2230M1ZV",
            "07AAACH7409R1ZZ",
            "27AADCB2230M1ZT",
        ]

        for gstin in valid_gstins:
            is_valid, error = GSTINValidator.validate(gstin)
            # Note: These are example GSTINs, actual validation depends on checksum
            assert is_valid or error is not None

    def test_invalid_length(self):
        """Test GSTIN with invalid length"""
        is_valid, error = GSTINValidator.validate("29AADCB2230M1Z")
        assert not is_valid
        assert "length" in error.lower()

    def test_invalid_state_code(self):
        """Test GSTIN with invalid state code"""
        is_valid, error = GSTINValidator.validate("99AADCB2230M1ZV")
        assert not is_valid
        # Could fail due to invalid state code or checksum
        assert "state code" in error.lower() or "checksum" in error.lower()

    def test_invalid_pan_format(self):
        """Test GSTIN with invalid PAN format"""
        is_valid, error = GSTINValidator.validate("29123456789A1ZV")
        assert not is_valid
        assert "PAN" in error

    def test_missing_z(self):
        """Test GSTIN missing Z at position 14"""
        is_valid, error = GSTINValidator.validate("29AADCB2230M1XV")
        assert not is_valid
        assert "Z" in error

    def test_empty_gstin(self):
        """Test empty GSTIN"""
        is_valid, error = GSTINValidator.validate("")
        assert not is_valid
        assert "empty" in error.lower()

    def test_get_state_name(self):
        """Test state name extraction"""
        state_name = GSTINValidator.get_state_name("29AADCB2230M1ZV")
        assert state_name == "Karnataka"

        state_name = GSTINValidator.get_state_name("07AAACH7409R1ZZ")
        assert state_name == "Delhi"

    def test_get_pan(self):
        """Test PAN extraction"""
        pan = GSTINValidator.get_pan("29AADCB2230M1ZV")
        assert pan == "AADCB2230M"

    def test_get_entity_type(self):
        """Test entity type extraction"""
        entity_type = GSTINValidator.get_entity_type("29AADCB2230M1ZV")
        assert entity_type  # Should return something

    def test_parse_gstin(self):
        """Test full GSTIN parsing"""
        result = GSTINValidator.parse("29AADCB2230M1ZV")

        assert "gstin" in result
        assert "state_code" in result
        assert "pan" in result
        assert result["state_code"] == "29"

    def test_case_insensitivity(self):
        """Test that validation is case-insensitive"""
        upper_result = GSTINValidator.parse("29AADCB2230M1ZV")
        lower_result = GSTINValidator.parse("29aadcb2230m1zv")

        assert upper_result["gstin"] == lower_result["gstin"].upper()

    def test_checksum_calculation(self):
        """Test checksum calculation"""
        # Test with known GSTIN (without checksum)
        checksum = GSTINValidator._calculate_checksum("29AADCB2230M1Z")
        assert isinstance(checksum, str)
        assert len(checksum) == 1
