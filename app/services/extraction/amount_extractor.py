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
            'tax', 'cgst', 'sgst', 'igst', 'utgst', 'cess',
            'tax demand', 'tax payable', 'tax due', 'tax liability',
            'central tax', 'state tax', 'integrated tax',
        ]
        self.penalty_keywords = [
            'penalty', 'fine', 'late fee', 'late filing fee',
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
        # Get context around the amount (150 chars before and after)
        start = max(0, position - 150)
        end = min(len(text), position + 50)
        context = text[start:end].lower()

        # Check for total first (takes precedence)
        for keyword in self.total_keywords:
            if keyword in context:
                return AmountType.TOTAL

        # Check for tax keywords
        for keyword in self.tax_keywords:
            if keyword in context:
                return AmountType.TAX

        # Check for penalty
        for keyword in self.penalty_keywords:
            if keyword in context:
                return AmountType.PENALTY

        # Check for interest
        for keyword in self.interest_keywords:
            if keyword in context:
                return AmountType.INTEREST

        # Check for refund
        for keyword in self.refund_keywords:
            if keyword in context:
                return AmountType.REFUND

        return AmountType.OTHER

    def identify_primary_amounts(
        self,
        amounts: List[AmountInfo]
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        Identify primary amounts from extracted list

        Returns:
            Tuple of (tax_amount, penalty_amount, interest_amount, total_amount)
        """
        tax_amount = None
        penalty_amount = None
        interest_amount = None
        total_amount = None

        # Group by type
        tax_amounts = [a for a in amounts if a.amount_type == AmountType.TAX]
        penalty_amounts = [a for a in amounts if a.amount_type == AmountType.PENALTY]
        interest_amounts = [a for a in amounts if a.amount_type == AmountType.INTEREST]
        total_amounts = [a for a in amounts if a.amount_type == AmountType.TOTAL]

        # Get largest of each type (usually the primary one)
        if tax_amounts:
            tax_amount = max(a.amount for a in tax_amounts)

        if penalty_amounts:
            penalty_amount = max(a.amount for a in penalty_amounts)

        if interest_amounts:
            interest_amount = max(a.amount for a in interest_amounts)

        if total_amounts:
            total_amount = max(a.amount for a in total_amounts)

        return tax_amount, penalty_amount, interest_amount, total_amount

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
