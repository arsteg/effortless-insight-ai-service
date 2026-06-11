"""
Main entity extractor service
"""

import re
from typing import Optional, List
import structlog

from app.services.extraction.patterns import EntityPatterns
from app.services.extraction.gstin_validator import GSTINValidator
from app.services.extraction.date_parser import DateParser
from app.services.extraction.amount_extractor import AmountExtractor
from app.schemas.entities import (
    ExtractedEntities,
    GSTINInfo,
    SectionReference,
)

logger = structlog.get_logger()


class EntityExtractor:
    """
    Main entity extractor for GST notices

    Extracts:
    - GSTINs with validation
    - Dates (issue, deadline, period)
    - Amounts (tax, penalty, interest)
    - Section/Rule references
    - Notice identifiers
    """

    def __init__(self):
        self.date_parser = DateParser()
        self.amount_extractor = AmountExtractor()

    async def extract(self, text: str) -> ExtractedEntities:
        """
        Extract all entities from notice text

        Args:
            text: OCR-extracted text from the notice

        Returns:
            ExtractedEntities with all extracted information
        """
        logger.info("Starting entity extraction", text_length=len(text))

        # Extract GSTINs
        gstins = self._extract_gstins(text)
        logger.debug(f"Found {len(gstins)} GSTINs")

        # Extract dates
        dates = self.date_parser.extract_dates(text)
        issue_date, response_deadline, period_from, period_to = \
            self.date_parser.identify_primary_dates(dates, text)
        logger.debug(f"Found {len(dates)} dates")

        # Extract amounts
        amounts = self.amount_extractor.extract_amounts(text)
        tax_amount, penalty_amount, interest_amount, total_amount = \
            self.amount_extractor.identify_primary_amounts(amounts)
        logger.debug(f"Found {len(amounts)} amounts")

        # Extract section references
        sections = self._extract_sections(text)
        logger.debug(f"Found {len(sections)} section references")

        # Extract notice identifiers
        notice_number = self._extract_notice_number(text)
        arn = self._extract_arn(text)
        din = self._extract_din(text)

        # Extract authority information
        issuing_authority = self._extract_authority(text)
        jurisdiction = self._extract_jurisdiction(text)

        # Determine primary GSTIN
        primary_gstin = None
        if gstins:
            # Prefer valid GSTINs
            valid_gstins = [g for g in gstins if g.is_valid]
            if valid_gstins:
                primary_gstin = valid_gstins[0].gstin
            else:
                primary_gstin = gstins[0].gstin

        entities = ExtractedEntities(
            gstins=gstins,
            dates=dates,
            amounts=amounts,
            sections=sections,
            primary_gstin=primary_gstin,
            issue_date=issue_date,
            response_deadline=response_deadline,
            period_from=period_from,
            period_to=period_to,
            tax_amount=tax_amount,
            penalty_amount=penalty_amount,
            interest_amount=interest_amount,
            total_amount=total_amount,
            notice_number=notice_number,
            arn=arn,
            din=din,
            issuing_authority=issuing_authority,
            jurisdiction=jurisdiction,
        )

        logger.info(
            "Entity extraction complete",
            gstins=len(gstins),
            dates=len(dates),
            amounts=len(amounts),
            sections=len(sections),
        )

        return entities

    def _extract_gstins(self, text: str) -> List[GSTINInfo]:
        """Extract and validate all GSTINs from text"""
        gstins = []

        for match in EntityPatterns.GSTIN.finditer(text):
            gstin = match.group(1).upper()
            is_valid, error = GSTINValidator.validate(gstin)

            gstins.append(GSTINInfo(
                gstin=gstin,
                is_valid=is_valid,
                state_code=gstin[:2] if len(gstin) >= 2 else "",
                state_name=GSTINValidator.get_state_name(gstin) or "",
                pan=GSTINValidator.get_pan(gstin) or "",
                entity_type=GSTINValidator.get_entity_type(gstin) or "",
                position_in_text=match.start(),
                confidence=0.95 if is_valid else 0.70,
            ))

        return gstins

    def _extract_sections(self, text: str) -> List[SectionReference]:
        """Extract section and rule references"""
        sections = []

        # Extract sections
        for match in EntityPatterns.SECTION.finditer(text):
            sections.append(SectionReference(
                reference=f"Section {match.group(1)}",
                reference_type="section",
                full_text=match.group(0),
                position_in_text=match.start(),
                confidence=0.90,
            ))

        # Extract rules
        for match in EntityPatterns.RULE.finditer(text):
            sections.append(SectionReference(
                reference=f"Rule {match.group(1)}",
                reference_type="rule",
                full_text=match.group(0),
                position_in_text=match.start(),
                confidence=0.90,
            ))

        # Extract notifications
        for match in EntityPatterns.NOTIFICATION.finditer(text):
            sections.append(SectionReference(
                reference=f"Notification {match.group(1)}",
                reference_type="notification",
                full_text=match.group(0),
                position_in_text=match.start(),
                confidence=0.85,
            ))

        # Extract circulars
        for match in EntityPatterns.CIRCULAR.finditer(text):
            sections.append(SectionReference(
                reference=f"Circular {match.group(1)}",
                reference_type="circular",
                full_text=match.group(0),
                position_in_text=match.start(),
                confidence=0.85,
            ))

        return sections

    def _extract_notice_number(self, text: str) -> Optional[str]:
        """Extract notice reference number"""
        match = EntityPatterns.NOTICE_NUMBER.search(text)
        if match:
            return match.group(1).strip()
        return None

    def _extract_arn(self, text: str) -> Optional[str]:
        """Extract Application Reference Number"""
        match = EntityPatterns.ARN.search(text)
        if match:
            return match.group(1).upper()
        return None

    def _extract_din(self, text: str) -> Optional[str]:
        """Extract Document Identification Number"""
        match = EntityPatterns.DIN.search(text)
        if match:
            return match.group(1).upper()
        return None

    def _extract_authority(self, text: str) -> Optional[str]:
        """Extract issuing authority name"""
        match = EntityPatterns.OFFICER.search(text)
        if match:
            return match.group(0).strip()
        return None

    def _extract_jurisdiction(self, text: str) -> Optional[str]:
        """Extract tax jurisdiction"""
        # Look for jurisdiction patterns
        patterns = [
            r'(?:Range|Division|Circle|Ward|Zone)[\s\-:]+([A-Za-z0-9\s\-]+)',
            r'(?:CGST|SGST)\s+([A-Za-z\s]+(?:Division|Range|Circle|Ward|Zone))',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def extract_notice_type(self, text: str) -> Optional[str]:
        """Extract notice type (DRC-01, ASMT-10, GSTR-3A, etc.)"""
        # Try different notice type patterns
        patterns = [
            (EntityPatterns.NOTICE_TYPE_DRC, "DRC"),
            (EntityPatterns.NOTICE_TYPE_ASMT, "ASMT"),
            (EntityPatterns.NOTICE_TYPE_REG, "REG"),
            (EntityPatterns.NOTICE_TYPE_RET, "RET"),
            (EntityPatterns.NOTICE_TYPE_GST, "GST"),
            (EntityPatterns.NOTICE_TYPE_GSTR, "GSTR"),
        ]

        for pattern, prefix in patterns:
            match = pattern.search(text)
            if match:
                notice_type = match.group(1).upper()
                # Normalize format
                notice_type = re.sub(r'[\s\-]+', '-', notice_type)
                return notice_type

        return None

    def extract_financial_year(self, text: str) -> Optional[str]:
        """Extract financial year reference"""
        match = EntityPatterns.FINANCIAL_YEAR.search(text)
        if match:
            fy = match.group(1)
            # Normalize format
            fy = re.sub(r'[\s\-]+', '-', fy)
            return f"FY {fy}"
        return None
