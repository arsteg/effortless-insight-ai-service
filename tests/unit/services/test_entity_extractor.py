"""
Unit tests for entity extractor
"""

import pytest
from datetime import date

from app.services.extraction.entity_extractor import EntityExtractor
from app.services.extraction.date_parser import DateParser
from app.services.extraction.amount_extractor import AmountExtractor


class TestEntityExtractor:
    """Test cases for entity extraction"""

    @pytest.fixture
    def extractor(self):
        return EntityExtractor()

    @pytest.fixture
    def sample_text(self):
        return """
        Notice Number: DRC-01/2024/123456
        GSTIN: 29AADCB2230M1ZV
        Date: 15/01/2024
        Deadline: 14/02/2024
        Amount: Rs. 5,00,000/-
        Total: ₹10,25,000
        Reference: Section 73 of CGST Act
        """

    @pytest.mark.asyncio
    async def test_extract_entities(self, extractor, sample_text):
        """Test full entity extraction"""
        entities = await extractor.extract(sample_text)

        assert entities is not None
        assert len(entities.gstins) > 0
        assert len(entities.dates) > 0
        assert len(entities.amounts) > 0

    @pytest.mark.asyncio
    async def test_extract_gstin(self, extractor, sample_text):
        """Test GSTIN extraction"""
        entities = await extractor.extract(sample_text)

        assert entities.primary_gstin is not None
        assert "29AADCB2230M1ZV" in entities.primary_gstin

    @pytest.mark.asyncio
    async def test_extract_multiple_gstins(self, extractor):
        """Test extraction of multiple GSTINs"""
        text = """
        Taxpayer GSTIN: 29AADCB2230M1ZV
        Related GSTIN: 07AAACH7409R1ZZ
        """
        entities = await extractor.extract(text)

        assert len(entities.gstins) >= 2

    @pytest.mark.asyncio
    async def test_extract_notice_type(self, extractor):
        """Test notice type extraction"""
        text = "This is a DRC-01 Show Cause Notice"
        notice_type = extractor.extract_notice_type(text)

        assert notice_type == "DRC-01"

    @pytest.mark.asyncio
    async def test_extract_various_notice_types(self, extractor):
        """Test extraction of various notice types"""
        test_cases = [
            ("ASMT-10 Scrutiny Notice", "ASMT-10"),
            ("REG-17 Cancellation", "REG-17"),
            ("Form GSTR-3A Non-filing", "GSTR-3A"),
        ]

        for text, expected in test_cases:
            result = extractor.extract_notice_type(text)
            assert result == expected, f"Expected {expected} for '{text}', got {result}"


class TestDateParser:
    """Test cases for date parsing"""

    @pytest.fixture
    def parser(self):
        return DateParser()

    def test_parse_dd_mm_yyyy(self, parser):
        """Test DD/MM/YYYY format"""
        text = "Date: 15/01/2024"
        dates = parser.extract_dates(text)

        assert len(dates) > 0
        assert dates[0].date == date(2024, 1, 15)

    def test_parse_dd_mm_yyyy_dash(self, parser):
        """Test DD-MM-YYYY format"""
        text = "Date: 15-01-2024"
        dates = parser.extract_dates(text)

        assert len(dates) > 0
        assert dates[0].date == date(2024, 1, 15)

    def test_parse_textual_date(self, parser):
        """Test textual date format"""
        text = "Date: 15 January 2024"
        dates = parser.extract_dates(text)

        assert len(dates) > 0
        assert dates[0].date == date(2024, 1, 15)

    def test_parse_abbreviated_month(self, parser):
        """Test abbreviated month format"""
        text = "Date: 15 Jan 2024"
        dates = parser.extract_dates(text)

        assert len(dates) > 0
        assert dates[0].date == date(2024, 1, 15)

    def test_identify_deadline(self, parser):
        """Test deadline identification"""
        text = "Please reply by 14/02/2024"
        dates = parser.extract_dates(text)

        assert len(dates) > 0
        # Check that deadline context is detected
        from app.schemas.entities import DateType
        deadline_dates = [d for d in dates if d.date_type == DateType.RESPONSE_DEADLINE]
        assert len(deadline_dates) > 0

    def test_parse_deadline_days(self, parser):
        """Test parsing deadline in days"""
        text = "Reply within 30 days"
        deadline = parser.parse_deadline_days(text, date(2024, 1, 15))

        assert deadline == date(2024, 2, 14)


class TestAmountExtractor:
    """Test cases for amount extraction"""

    @pytest.fixture
    def extractor(self):
        return AmountExtractor()

    def test_extract_rupee_symbol(self, extractor):
        """Test ₹ symbol amount"""
        text = "Amount: ₹5,00,000"
        amounts = extractor.extract_amounts(text)

        assert len(amounts) > 0
        assert amounts[0].amount == 500000.0

    def test_extract_rs(self, extractor):
        """Test Rs. amount"""
        text = "Amount: Rs. 5,00,000/-"
        amounts = extractor.extract_amounts(text)

        assert len(amounts) > 0
        assert amounts[0].amount == 500000.0

    def test_extract_inr(self, extractor):
        """Test INR amount"""
        text = "Amount: INR 500000"
        amounts = extractor.extract_amounts(text)

        assert len(amounts) > 0
        assert amounts[0].amount == 500000.0

    def test_extract_lakhs(self, extractor):
        """Test amount in lakhs"""
        text = "Amount: 5 Lakhs"
        amounts = extractor.extract_amounts(text)

        assert len(amounts) > 0
        assert amounts[0].amount == 500000.0

    def test_extract_crores(self, extractor):
        """Test amount in crores"""
        text = "Amount: 1.5 Crore"
        amounts = extractor.extract_amounts(text)

        assert len(amounts) > 0
        assert amounts[0].amount == 15000000.0

    def test_identify_tax_amount(self, extractor):
        """Test tax amount identification"""
        text = "CGST Tax Amount: Rs. 5,00,000"
        amounts = extractor.extract_amounts(text)

        assert len(amounts) > 0
        from app.schemas.entities import AmountType
        assert amounts[0].amount_type == AmountType.TAX

    def test_identify_penalty(self, extractor):
        """Test penalty identification"""
        text = "Penalty: Rs. 50,000"
        amounts = extractor.extract_amounts(text)

        assert len(amounts) > 0
        from app.schemas.entities import AmountType
        assert amounts[0].amount_type == AmountType.PENALTY

    def test_format_indian_currency(self, extractor):
        """Test Indian currency formatting"""
        formatted = extractor.format_indian_currency(1234567.89)
        assert formatted == "₹12,34,567.89"
