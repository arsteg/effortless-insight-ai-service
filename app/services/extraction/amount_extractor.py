"""
Amount extractor for GST notices
"""

import re
from typing import List, Optional, Tuple
import structlog

from app.services.extraction.patterns import EntityPatterns
from app.schemas.entities import AmountInfo, AmountType

logger = structlog.get_logger()


class AmountExtractor:
    """
    Extract monetary amounts from GST notices

    Supports various Indian currency formats:
    - ₹ symbol
    - Rs. / Rupees
    - INR
    - Lakhs/Crores notation
    """

    def __init__(self):
        # Keywords to identify amount types
        self.tax_keywords = [
            'tax', 'cgst', 'sgst', 'igst', 'utgst',
            'tax demand', 'tax payable', 'tax due', 'tax liability',
            'central tax', 'state tax', 'integrated tax',
        ]
        self.penalty_keywords = [
            'penalty', 'fine',
            'penalty payable', 'penalty amount',
        ]
        self.interest_keywords = [
            'interest', 'interest payable', 'interest amount',
            'interest due', 'interest @', 'interest at',
        ]
        self.total_keywords = [
            'total', 'total amount', 'total demand', 'total liability',
            'aggregate', 'sum total', 'grand total',
        ]
        self.refund_keywords = [
            'refund', 'refundable', 'excess', 'credit',
        ]
        self.late_fee_keywords = [
            'late fee', 'late filing fee', 'late filing', 'delay fee',
            'late payment fee', 'lateness fee', 'late return fee',
        ]
        self.cess_keywords = [
            'cess', 'compensation cess', 'gst cess', 'coal cess',
            'swachh bharat cess', 'krishi kalyan cess',
        ]

    def extract_amounts(self, text: str) -> List[AmountInfo]:
        """
        Extract all amounts from text

        Args:
            text: Text to search for amounts

        Returns:
            List of AmountInfo objects
        """
        amounts = []

        # Extract using different patterns
        amounts.extend(self._extract_rupee_symbol(text))
        amounts.extend(self._extract_rs_amounts(text))
        amounts.extend(self._extract_inr_amounts(text))
        amounts.extend(self._extract_rupees_word(text))
        amounts.extend(self._extract_lakhs_crores(text))

        # Remove duplicates and sort by position
        seen = set()
        unique_amounts = []
        for amt in sorted(amounts, key=lambda x: x.position_in_text):
            key = (amt.amount, amt.position_in_text)
            if key not in seen:
                seen.add(key)
                unique_amounts.append(amt)

        return unique_amounts

    def _extract_rupee_symbol(self, text: str) -> List[AmountInfo]:
        """Extract amounts with ₹ symbol"""
        amounts = []

        for match in EntityPatterns.AMOUNT_RUPEE_SYMBOL.finditer(text):
            amount = self._parse_amount_string(match.group(1))
            if amount is not None:
                amount_type = self._infer_amount_type(text, match.start())
                amounts.append(AmountInfo(
                    amount=amount,
                    amount_type=amount_type,
                    original_text=match.group(0),
                    position_in_text=match.start(),
                    confidence=0.95,
                ))

        return amounts

    def _extract_rs_amounts(self, text: str) -> List[AmountInfo]:
        """Extract amounts with Rs. prefix"""
        amounts = []

        for match in EntityPatterns.AMOUNT_RS.finditer(text):
            amount = self._parse_amount_string(match.group(1))
            if amount is not None:
                amount_type = self._infer_amount_type(text, match.start())
                amounts.append(AmountInfo(
                    amount=amount,
                    amount_type=amount_type,
                    original_text=match.group(0),
                    position_in_text=match.start(),
                    confidence=0.90,
                ))

        return amounts

    def _extract_inr_amounts(self, text: str) -> List[AmountInfo]:
        """Extract amounts with INR prefix"""
        amounts = []

        for match in EntityPatterns.AMOUNT_INR.finditer(text):
            amount = self._parse_amount_string(match.group(1))
            if amount is not None:
                amount_type = self._infer_amount_type(text, match.start())
                amounts.append(AmountInfo(
                    amount=amount,
                    amount_type=amount_type,
                    original_text=match.group(0),
                    position_in_text=match.start(),
                    confidence=0.90,
                ))

        return amounts

    def _extract_rupees_word(self, text: str) -> List[AmountInfo]:
        """Extract amounts with 'Rupees' word"""
        amounts = []

        for match in EntityPatterns.AMOUNT_RUPEES.finditer(text):
            amount = self._parse_amount_string(match.group(1))
            if amount is not None:
                amount_type = self._infer_amount_type(text, match.start())
                amounts.append(AmountInfo(
                    amount=amount,
                    amount_type=amount_type,
                    original_text=match.group(0),
                    position_in_text=match.start(),
                    confidence=0.85,
                ))

        return amounts

    def _extract_lakhs_crores(self, text: str) -> List[AmountInfo]:
        """Extract amounts in lakhs/crores notation"""
        amounts = []

        # Lakhs
        for match in EntityPatterns.AMOUNT_LAKHS.finditer(text):
            base_amount = self._parse_amount_string(match.group(1))
            if base_amount is not None:
                amount = base_amount * 100000  # 1 lakh = 100,000
                amount_type = self._infer_amount_type(text, match.start())
                amounts.append(AmountInfo(
                    amount=amount,
                    amount_type=amount_type,
                    original_text=match.group(0),
                    position_in_text=match.start(),
                    confidence=0.85,
                ))

        # Crores
        for match in EntityPatterns.AMOUNT_CRORES.finditer(text):
            base_amount = self._parse_amount_string(match.group(1))
            if base_amount is not None:
                amount = base_amount * 10000000  # 1 crore = 10,000,000
                amount_type = self._infer_amount_type(text, match.start())
                amounts.append(AmountInfo(
                    amount=amount,
                    amount_type=amount_type,
                    original_text=match.group(0),
                    position_in_text=match.start(),
                    confidence=0.85,
                ))

        return amounts

    def _parse_amount_string(self, amount_str: str) -> Optional[float]:
        """
        Parse amount string to float

        Handles Indian comma notation (1,00,000 = 100000)
        """
        try:
            # Remove commas
            clean = amount_str.replace(',', '')

            # Handle decimal
            amount = float(clean)

            # Sanity check - amounts should be positive and reasonable
            if amount <= 0 or amount > 1e15:
                return None

            return round(amount, 2)

        except (ValueError, TypeError):
            return None

    def _infer_amount_type(self, text: str, position: int) -> AmountType:
        """
        Infer the type of amount based on surrounding context

        Args:
            text: Full text
            position: Position of the amount in text

        Returns:
            Inferred AmountType
        """
        # Prefer the closest label before the amount on the same line.
        # A wide keyword window lets adjacent rows (especially Total/Tax)
        # incorrectly classify every amount in a compact demand table.
        groups = [
            (AmountType.TOTAL, self.total_keywords),
            (AmountType.LATE_FEE, self.late_fee_keywords),
            (AmountType.CESS, self.cess_keywords),
            (AmountType.PENALTY, self.penalty_keywords),
            (AmountType.INTEREST, self.interest_keywords),
            (AmountType.TAX, self.tax_keywords),
            (AmountType.REFUND, self.refund_keywords),
            (AmountType.OTHER_CHARGES, ['other charges', 'other charge', 'administrative charges']),
        ]
        line_start = text.rfind('\n', 0, position) + 1
        context = text[max(line_start, position - 150):position].lower()
        matches = []
        for amount_type, keywords in groups:
            for keyword in keywords:
                for match in re.finditer(r'\b' + re.escape(keyword) + r'\b', context):
                    matches.append((match.end(), len(keyword), amount_type))
        if matches:
            return max(matches, key=lambda item: (item[0], item[1]))[2]
        return AmountType.OTHER

    def identify_primary_amounts(
        self,
        amounts: List[AmountInfo]
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float],
               Optional[float], Optional[float], Optional[float]]:
        """
        Identify primary amounts from extracted list

        Returns:
            Tuple of (tax_amount, penalty_amount, interest_amount, total_amount,
                      late_fee_amount, cess_amount, other_charges_amount)
        """
        tax_amount = None
        penalty_amount = None
        interest_amount = None
        total_amount = None
        late_fee_amount = None
        cess_amount = None
        other_charges_amount = None

        # Group by type
        tax_amounts = [a for a in amounts if a.amount_type == AmountType.TAX]
        penalty_amounts = [a for a in amounts if a.amount_type == AmountType.PENALTY]
        interest_amounts = [a for a in amounts if a.amount_type == AmountType.INTEREST]
        total_amounts = [a for a in amounts if a.amount_type == AmountType.TOTAL]
        late_fee_amounts = [a for a in amounts if a.amount_type == AmountType.LATE_FEE]
        cess_amounts = [a for a in amounts if a.amount_type == AmountType.CESS]
        other_amounts = [a for a in amounts if a.amount_type == AmountType.OTHER_CHARGES]

        # Get largest of each type (usually the primary one)
        if tax_amounts:
            tax_amount = max(a.amount for a in tax_amounts)

        if penalty_amounts:
            penalty_amount = max(a.amount for a in penalty_amounts)

        if interest_amounts:
            interest_amount = max(a.amount for a in interest_amounts)

        if total_amounts:
            total_amount = max(a.amount for a in total_amounts)

        if late_fee_amounts:
            late_fee_amount = max(a.amount for a in late_fee_amounts)

        if cess_amounts:
            cess_amount = max(a.amount for a in cess_amounts)

        # Only explicitly labelled charges count; unclassified amounts may be turnover.
        if other_amounts:
            other_charges_amount = sum(a.amount for a in other_amounts)

        return (tax_amount, penalty_amount, interest_amount, total_amount,
                late_fee_amount, cess_amount, other_charges_amount)

    def format_indian_currency(self, amount: float) -> str:
        """
        Format amount in Indian currency notation

        E.g., 1234567.89 -> ₹12,34,567.89
        """
        if amount < 0:
            return f"-₹{self.format_indian_currency(-amount)[1:]}"

        # Split integer and decimal parts
        amount_str = f"{amount:.2f}"
        integer_part, decimal_part = amount_str.split('.')

        # Format integer part with Indian comma system
        if len(integer_part) <= 3:
            formatted = integer_part
        else:
            # Last 3 digits
            formatted = integer_part[-3:]
            # Rest in groups of 2
            remaining = integer_part[:-3]
            while remaining:
                formatted = remaining[-2:] + ',' + formatted
                remaining = remaining[:-2]

        return f"₹{formatted}.{decimal_part}"
