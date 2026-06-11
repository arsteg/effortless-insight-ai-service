"""
Fact checker for verifying extracted information against source text
"""

import re
from typing import List, Tuple, Optional
from datetime import date
import structlog

from app.schemas.entities import ExtractedEntities
from app.services.extraction.gstin_validator import GSTINValidator

logger = structlog.get_logger()


class FactChecker:
    """
    Verify that extracted facts exist in the original text

    Verification Rules:
    1. Deadlines must exist in original OCR text
    2. Amounts must match extracted values (±1% tolerance)
    3. Section references must be valid GST sections
    4. GSTIN must pass checksum validation
    5. Dates must be logically consistent (issue < deadline)
    """

    # Valid GST sections (most common)
    VALID_GST_SECTIONS = {
        # CGST Act sections
        "7", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
        "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34",
        "35", "37", "38", "39", "40", "41", "42", "43", "44", "45", "46", "47", "48",
        "49", "50", "51", "52", "53", "54", "55", "56", "57", "58", "59", "60", "61",
        "62", "63", "64", "65", "66", "67", "68", "69", "70", "71", "72", "73", "74",
        "75", "76", "77", "78", "79", "80", "81", "82", "83", "84", "85", "86", "87",
        "88", "89", "90", "91", "92", "93", "94", "95", "96", "97", "98", "99", "100",
        "101", "102", "103", "104", "105", "106", "107", "108", "109", "110",
        "111", "112", "113", "114", "115", "116", "117", "118", "119", "120",
        "121", "122", "123", "124", "125", "126", "127", "128", "129", "130",
        "131", "132", "133", "134", "135", "136", "137", "138", "139", "140",
        "141", "142", "143", "144", "145", "146", "147", "148", "149", "150",
        "151", "152", "153", "154", "155", "156", "157", "158", "159", "160",
        "161", "162", "163", "164", "165", "166", "167", "168", "169", "170",
        "171", "172", "173", "174",
    }

    # Valid GST Rules
    VALID_GST_RULES = {str(i) for i in range(1, 165)}

    def __init__(self, amount_tolerance: float = 0.01):
        """
        Initialize fact checker

        Args:
            amount_tolerance: Tolerance for amount matching (default 1%)
        """
        self.amount_tolerance = amount_tolerance

    def verify_all(
        self,
        original_text: str,
        entities: ExtractedEntities,
        llm_output: dict,
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Run all verification checks

        Args:
            original_text: Original OCR text
            entities: Extracted entities
            llm_output: LLM analysis output

        Returns:
            Tuple of (all_valid, issues, warnings)
        """
        issues = []
        warnings = []

        # 1. Verify GSTIN
        gstin_valid, gstin_issue = self.verify_gstin(entities)
        if not gstin_valid:
            issues.append(gstin_issue)

        # 2. Verify deadline in text
        deadline_valid, deadline_msg = self.verify_deadline_in_text(
            original_text, entities.response_deadline
        )
        if not deadline_valid:
            if entities.response_deadline:
                warnings.append(deadline_msg)

        # 3. Verify amounts match
        amount_issues = self.verify_amounts(original_text, entities, llm_output)
        issues.extend(amount_issues)

        # 4. Verify section references
        section_issues = self.verify_sections(entities)
        warnings.extend(section_issues)

        # 5. Verify date consistency
        date_valid, date_issue = self.verify_date_consistency(entities)
        if not date_valid:
            issues.append(date_issue)

        all_valid = len(issues) == 0

        logger.info(
            "Fact check complete",
            valid=all_valid,
            issues=len(issues),
            warnings=len(warnings)
        )

        return all_valid, issues, warnings

    def verify_gstin(self, entities: ExtractedEntities) -> Tuple[bool, Optional[str]]:
        """Verify GSTIN checksum"""
        if not entities.primary_gstin:
            return True, None  # No GSTIN to verify

        is_valid, error = GSTINValidator.validate(entities.primary_gstin)
        if not is_valid:
            return False, f"GSTIN checksum invalid: {error}"

        return True, None

    def verify_deadline_in_text(
        self,
        original_text: str,
        deadline: Optional[date]
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify that deadline date appears in original text

        The exact date should be findable in the original OCR text.
        """
        if deadline is None:
            return True, None

        # Format date in various ways (use platform-independent approach for no-padding)
        day = deadline.day
        month = deadline.month
        year = deadline.year
        month_name = deadline.strftime("%B")
        month_abbr = deadline.strftime("%b")

        date_formats = [
            f"{day:02d}/{month:02d}/{year}",
            f"{day:02d}-{month:02d}-{year}",
            f"{day:02d}.{month:02d}.{year}",
            f"{day}/{month:02d}/{year}",  # No leading zero on day
            f"{day}-{month}-{year}",  # No leading zeros
            f"{day:02d} {month_name} {year}",
            f"{day:02d} {month_abbr} {year}",
            f"{day} {month_name} {year}",  # No leading zero on day
            f"{day} {month_abbr} {year}",  # No leading zero on day
        ]

        # Check if any format appears in text
        text_lower = original_text.lower()
        for fmt in date_formats:
            if fmt.lower() in text_lower:
                return True, None

        # Check for partial matches
        day = deadline.day
        month = deadline.month
        year = deadline.year

        # Pattern for the date components
        partial_pattern = rf'\b{day}[/\-\.]\s*{month}[/\-\.]\s*{year}\b'
        if re.search(partial_pattern, original_text, re.IGNORECASE):
            return True, None

        return False, f"Deadline {deadline.strftime('%d/%m/%Y')} not found in original text"

    def verify_amounts(
        self,
        original_text: str,
        entities: ExtractedEntities,
        llm_output: dict,
    ) -> List[str]:
        """
        Verify that amounts match between entities and LLM output

        Uses tolerance for matching.
        """
        issues = []

        # Get LLM reported amounts
        llm_metadata = llm_output.get("metadata", {})
        llm_tax = llm_metadata.get("tax_amount")
        llm_penalty = llm_metadata.get("penalty_amount")
        llm_interest = llm_metadata.get("interest_amount")

        # Compare with entity amounts
        if llm_tax is not None and entities.tax_amount is not None:
            if not self._amounts_match(llm_tax, entities.tax_amount):
                issues.append(
                    f"Tax amount mismatch: LLM={llm_tax}, Entity={entities.tax_amount}"
                )

        if llm_penalty is not None and entities.penalty_amount is not None:
            if not self._amounts_match(llm_penalty, entities.penalty_amount):
                issues.append(
                    f"Penalty amount mismatch: LLM={llm_penalty}, Entity={entities.penalty_amount}"
                )

        if llm_interest is not None and entities.interest_amount is not None:
            if not self._amounts_match(llm_interest, entities.interest_amount):
                issues.append(
                    f"Interest amount mismatch: LLM={llm_interest}, Entity={entities.interest_amount}"
                )

        return issues

    def _amounts_match(self, amount1: float, amount2: float) -> bool:
        """Check if two amounts match within tolerance"""
        if amount1 == 0 and amount2 == 0:
            return True

        max_amt = max(abs(amount1), abs(amount2))
        diff = abs(amount1 - amount2)

        return diff / max_amt <= self.amount_tolerance

    def verify_sections(self, entities: ExtractedEntities) -> List[str]:
        """Verify that section references are valid GST sections"""
        warnings = []

        for section in entities.sections:
            ref = section.reference

            # Extract section/rule number
            match = re.search(r'(?:Section|Rule)\s*(\d+)', ref, re.IGNORECASE)
            if match:
                number = match.group(1)

                if 'section' in ref.lower():
                    if number not in self.VALID_GST_SECTIONS:
                        warnings.append(f"Unrecognized section: {ref}")
                elif 'rule' in ref.lower():
                    if number not in self.VALID_GST_RULES:
                        warnings.append(f"Unrecognized rule: {ref}")

        return warnings

    def verify_date_consistency(
        self,
        entities: ExtractedEntities
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify dates are logically consistent

        - Issue date should be before deadline
        - Period from should be before period to
        - Issue date should be after period to (usually)
        """
        # Issue date vs deadline
        if entities.issue_date and entities.response_deadline:
            if entities.issue_date > entities.response_deadline:
                return False, f"Issue date ({entities.issue_date}) is after deadline ({entities.response_deadline})"

        # Period from vs period to
        if entities.period_from and entities.period_to:
            if entities.period_from > entities.period_to:
                return False, f"Period from ({entities.period_from}) is after period to ({entities.period_to})"

        # Issue date should generally be after or around period to
        if entities.issue_date and entities.period_to:
            # Allow some flexibility (notice can be issued slightly before period ends)
            from datetime import timedelta
            if entities.issue_date < entities.period_to - timedelta(days=30):
                return False, f"Issue date ({entities.issue_date}) is significantly before period end ({entities.period_to})"

        return True, None

    def verify_text_presence(
        self,
        original_text: str,
        claim: str,
        min_words: int = 2
    ) -> bool:
        """
        Verify that key parts of a claim exist in the original text

        Args:
            original_text: Original OCR text
            claim: Claim to verify
            min_words: Minimum words that must match

        Returns:
            True if claim can be substantiated
        """
        # Tokenize claim
        words = re.findall(r'\b\w+\b', claim.lower())
        text_lower = original_text.lower()

        # Count matches
        matches = sum(1 for word in words if word in text_lower and len(word) > 3)

        return matches >= min_words
