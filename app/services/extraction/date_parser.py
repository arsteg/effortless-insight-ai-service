"""
Date parser for Indian date formats
"""

import re
from datetime import date, datetime
from typing import Optional, List, Tuple
import structlog

from app.services.extraction.patterns import EntityPatterns
from app.schemas.entities import DateInfo, DateType

logger = structlog.get_logger()

# Month name mappings
MONTH_NAMES = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}


class DateParser:
    """
    Parser for dates in Indian formats

    Supports:
    - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    - DD Mon YYYY, DD Month YYYY
    - YYYY-MM-DD (ISO format)
    """

    def __init__(self):
        self.deadline_keywords = [
            'within', 'by', 'before', 'on or before', 'not later than',
            'deadline', 'due date', 'due on', 'reply by', 'respond by',
            'submission date', 'last date',
        ]
        self.issue_keywords = [
            'dated', 'date of issue', 'issued on', 'issued dated',
            'notice date', 'order date',
        ]
        self.period_keywords = [
            'period from', 'period:', 'tax period', 'for the period',
            'financial year', 'fy', 'f.y.',
        ]

    def extract_dates(self, text: str) -> List[DateInfo]:
        """
        Extract all dates from text

        Args:
            text: Text to search for dates

        Returns:
            List of DateInfo objects
        """
        dates = []

        # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
        dates.extend(self._extract_dd_mm_yyyy(text))

        # DD Mon YYYY or DD Month YYYY
        dates.extend(self._extract_dd_mon_yyyy(text))

        # YYYY-MM-DD (ISO format)
        dates.extend(self._extract_iso_dates(text))

        # Remove duplicates (same date at same position)
        seen = set()
        unique_dates = []
        for d in dates:
            key = (d.date, d.position_in_text)
            if key not in seen:
                seen.add(key)
                unique_dates.append(d)

        return unique_dates

    def _extract_dd_mm_yyyy(self, text: str) -> List[DateInfo]:
        """Extract DD/MM/YYYY format dates"""
        dates = []

        for match in EntityPatterns.DATE_DD_MM_YYYY.finditer(text):
            try:
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))

                if self._is_valid_date(day, month, year):
                    parsed_date = date(year, month, day)
                    date_type = self._infer_date_type(text, match.start())

                    dates.append(DateInfo(
                        date=parsed_date,
                        date_type=date_type,
                        original_text=match.group(0),
                        position_in_text=match.start(),
                        confidence=0.95,
                    ))

            except (ValueError, IndexError):
                continue

        return dates

    def _extract_dd_mon_yyyy(self, text: str) -> List[DateInfo]:
        """Extract DD Mon YYYY format dates"""
        dates = []

        for match in EntityPatterns.DATE_DD_MON_YYYY.finditer(text):
            try:
                day = int(match.group(1))
                month_str = match.group(2).lower()
                year = int(match.group(3))

                month = MONTH_NAMES.get(month_str)
                if not month:
                    # Try abbreviated form
                    month = MONTH_NAMES.get(month_str[:3])

                if month and self._is_valid_date(day, month, year):
                    parsed_date = date(year, month, day)
                    date_type = self._infer_date_type(text, match.start())

                    dates.append(DateInfo(
                        date=parsed_date,
                        date_type=date_type,
                        original_text=match.group(0),
                        position_in_text=match.start(),
                        confidence=0.95,
                    ))

            except (ValueError, IndexError):
                continue

        return dates

    def _extract_iso_dates(self, text: str) -> List[DateInfo]:
        """Extract YYYY-MM-DD format dates"""
        dates = []

        for match in EntityPatterns.DATE_YYYY_MM_DD.finditer(text):
            try:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))

                if self._is_valid_date(day, month, year):
                    parsed_date = date(year, month, day)
                    date_type = self._infer_date_type(text, match.start())

                    dates.append(DateInfo(
                        date=parsed_date,
                        date_type=date_type,
                        original_text=match.group(0),
                        position_in_text=match.start(),
                        confidence=0.90,  # Slightly lower confidence for ISO
                    ))

            except (ValueError, IndexError):
                continue

        return dates

    def _is_valid_date(self, day: int, month: int, year: int) -> bool:
        """Check if date components form a valid date"""
        if not (1 <= month <= 12):
            return False
        if not (1 <= day <= 31):
            return False
        if not (1990 <= year <= 2100):
            return False

        try:
            date(year, month, day)
            return True
        except ValueError:
            return False

    def _infer_date_type(self, text: str, position: int) -> DateType:
        """
        Infer the type of date based on surrounding context

        Args:
            text: Full text
            position: Position of the date in text

        Returns:
            Inferred DateType
        """
        # Get context around the date (100 chars before)
        start = max(0, position - 100)
        context = text[start:position].lower()

        # Check for deadline keywords
        for keyword in self.deadline_keywords:
            if keyword in context:
                return DateType.RESPONSE_DEADLINE

        # Check for issue date keywords
        for keyword in self.issue_keywords:
            if keyword in context:
                return DateType.ISSUE_DATE

        # Check for period keywords
        for keyword in self.period_keywords:
            if keyword in context:
                return DateType.PERIOD_FROM  # Default to period_from

        return DateType.OTHER

    def parse_deadline_days(self, text: str, reference_date: Optional[date] = None) -> Optional[date]:
        """
        Parse deadline expressed in days (e.g., "within 30 days")

        Args:
            text: Text containing deadline
            reference_date: Reference date (default: today)

        Returns:
            Calculated deadline date or None
        """
        if reference_date is None:
            reference_date = date.today()

        match = EntityPatterns.DAYS_PATTERN.search(text)
        if match:
            days = int(match.group(1))
            from datetime import timedelta
            return reference_date + timedelta(days=days)

        return None

    def identify_primary_dates(
        self,
        dates: List[DateInfo],
        text: str
    ) -> Tuple[Optional[date], Optional[date], Optional[date], Optional[date]]:
        """
        Identify primary dates from a list of extracted dates

        Returns:
            Tuple of (issue_date, response_deadline, period_from, period_to)
        """
        issue_date = None
        response_deadline = None
        period_from = None
        period_to = None

        # Sort dates by type confidence and recency
        issue_dates = [d for d in dates if d.date_type == DateType.ISSUE_DATE]
        deadline_dates = [d for d in dates if d.date_type == DateType.RESPONSE_DEADLINE]
        period_dates = [d for d in dates if d.date_type == DateType.PERIOD_FROM]

        # Get the most recent issue date
        if issue_dates:
            issue_dates.sort(key=lambda x: x.date, reverse=True)
            issue_date = issue_dates[0].date

        # Get the most recent deadline
        if deadline_dates:
            deadline_dates.sort(key=lambda x: x.date, reverse=True)
            response_deadline = deadline_dates[0].date

        # Get period dates
        if len(period_dates) >= 2:
            period_dates.sort(key=lambda x: x.date)
            period_from = period_dates[0].date
            period_to = period_dates[-1].date
        elif len(period_dates) == 1:
            period_from = period_dates[0].date

        # If no deadline found, try to find one from days pattern
        if not response_deadline:
            deadline = self.parse_deadline_days(text, issue_date)
            if deadline:
                response_deadline = deadline

        return issue_date, response_deadline, period_from, period_to
