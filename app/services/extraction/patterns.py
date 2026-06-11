"""
Regex patterns for entity extraction
"""

import re
from typing import Pattern


class EntityPatterns:
    """
    Centralized regex patterns for GST notice entity extraction
    """

    # GSTIN Pattern: 2-digit state code + 10-char PAN + 1-char entity code + Z + checksum
    # Format: SSPPPPPPPPPPEZC
    GSTIN: Pattern = re.compile(
        r'\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d])\b',
        re.IGNORECASE
    )

    # PAN Pattern: 5 letters + 4 digits + 1 letter
    PAN: Pattern = re.compile(
        r'\b([A-Z]{5}\d{4}[A-Z])\b',
        re.IGNORECASE
    )

    # Date patterns (Indian format)
    DATE_DD_MM_YYYY: Pattern = re.compile(
        r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b'
    )

    DATE_DD_MON_YYYY: Pattern = re.compile(
        r'\b(\d{1,2})[\s\-]*(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'[\s\-,]*(\d{4})\b',
        re.IGNORECASE
    )

    DATE_YYYY_MM_DD: Pattern = re.compile(
        r'\b(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})\b'
    )

    # Amount patterns
    AMOUNT_RUPEE_SYMBOL: Pattern = re.compile(
        r'₹\s*([\d,]+(?:\.\d{1,2})?)',
        re.UNICODE
    )

    AMOUNT_RS: Pattern = re.compile(
        r'Rs\.?\s*([\d,]+(?:\.\d{1,2})?)',
        re.IGNORECASE
    )

    AMOUNT_INR: Pattern = re.compile(
        r'INR\s*([\d,]+(?:\.\d{1,2})?)',
        re.IGNORECASE
    )

    AMOUNT_RUPEES: Pattern = re.compile(
        r'(?:Rupees|rupees)\s*([\d,]+(?:\.\d{1,2})?)',
        re.IGNORECASE
    )

    # Large amounts in lakhs/crores
    AMOUNT_LAKHS: Pattern = re.compile(
        r'([\d,]+(?:\.\d{1,2})?)\s*(?:Lakhs?|Lacs?|L)\b',
        re.IGNORECASE
    )

    AMOUNT_CRORES: Pattern = re.compile(
        r'([\d,]+(?:\.\d{1,2})?)\s*(?:Crores?|Cr)\b',
        re.IGNORECASE
    )

    # Section references
    SECTION: Pattern = re.compile(
        r'(?:Section|Sec\.?|S\.?)\s*(\d+(?:\([a-zA-Z0-9]+\))?(?:\s*(?:read\s+with|r/w|r\.w\.)\s*(?:Section|Sec\.?|S\.?)\s*\d+(?:\([a-zA-Z0-9]+\))?)*)',
        re.IGNORECASE
    )

    RULE: Pattern = re.compile(
        r'(?:Rule)\s*(\d+(?:\([a-zA-Z0-9]+\))?)',
        re.IGNORECASE
    )

    NOTIFICATION: Pattern = re.compile(
        r'(?:Notification\s+No\.?|Notfn\.?)\s*(\d+[/\-]\d{4})',
        re.IGNORECASE
    )

    CIRCULAR: Pattern = re.compile(
        r'(?:Circular\s+No\.?)\s*(\d+[/\-]\d+[/\-]\d{4})',
        re.IGNORECASE
    )

    # Notice identifiers
    NOTICE_NUMBER: Pattern = re.compile(
        r'(?:Notice\s+No\.?|Ref\.?\s*No\.?|Reference\s+No\.?)\s*[:\s]*([A-Z0-9\-/]+)',
        re.IGNORECASE
    )

    ARN: Pattern = re.compile(
        r'\b(AA\d{2}\d{4}\d{6}[A-Z\d]{3})\b',
        re.IGNORECASE
    )

    DIN: Pattern = re.compile(
        r'\b(DIN\d{16,20})\b',
        re.IGNORECASE
    )

    # Notice types
    NOTICE_TYPE_DRC: Pattern = re.compile(
        r'(DRC[\-\s]?(?:01|01A|02|03|04|05|06|07|08|09|10|11|12|13))',
        re.IGNORECASE
    )

    NOTICE_TYPE_ASMT: Pattern = re.compile(
        r'(ASMT[\-\s]?(?:10|11|12|13|14|15|16|17|18))',
        re.IGNORECASE
    )

    NOTICE_TYPE_REG: Pattern = re.compile(
        r'(REG[\-\s]?(?:01|02|03|04|05|06|07|08|09|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25))',
        re.IGNORECASE
    )

    NOTICE_TYPE_RET: Pattern = re.compile(
        r'(RET[\-\s]?(?:01|02|03))',
        re.IGNORECASE
    )

    NOTICE_TYPE_GST: Pattern = re.compile(
        r'(GST[\-\s]?(?:RFD|PMT|REG|INS|MIS|APL|ADT|RCM|EWB|CPD)[\-\s]?\d{2})',
        re.IGNORECASE
    )

    NOTICE_TYPE_GSTR: Pattern = re.compile(
        r'(GSTR[\-\s]?(?:1|2A|2B|3A|3B|4|5|5A|6|7|8|9|9A|9C|10|11))',
        re.IGNORECASE
    )

    # Tax periods
    FINANCIAL_YEAR: Pattern = re.compile(
        r'(?:FY|F\.Y\.?|Financial\s+Year)\s*[\s:]*(\d{4}[\-\s]*\d{2,4})',
        re.IGNORECASE
    )

    TAX_PERIOD: Pattern = re.compile(
        r'(?:Tax\s+Period|Period)[\s:]+([A-Z][a-z]+[\s\-]+\d{4})\s*(?:to|[-])\s*([A-Z][a-z]+[\s\-]+\d{4})',
        re.IGNORECASE
    )

    # Authority names
    OFFICER: Pattern = re.compile(
        r'(?:Officer|Authority|Commissioner|Assistant\s+Commissioner|Deputy\s+Commissioner|'
        r'Joint\s+Commissioner|Additional\s+Commissioner|Principal\s+Commissioner|'
        r'Superintendent|Inspector)(?:\s+of\s+(?:CGST|SGST|GST|Central\s+Tax|State\s+Tax))?'
        r'(?:\s*,?\s*[A-Za-z\s]+(?:Division|Range|Circle|Ward|Zone))?',
        re.IGNORECASE
    )

    # Email
    EMAIL: Pattern = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )

    # Phone numbers (Indian)
    PHONE: Pattern = re.compile(
        r'(?:\+91[\-\s]?)?(?:\d{5}[\-\s]?\d{5}|\d{10}|\d{4}[\-\s]?\d{6})'
    )

    # Keywords for amount types
    TAX_AMOUNT_KEYWORDS: Pattern = re.compile(
        r'(?:Tax|CGST|SGST|IGST|UTGST|Cess)[\s:]+(?:Amount|Payable|Due|Demand)',
        re.IGNORECASE
    )

    PENALTY_KEYWORDS: Pattern = re.compile(
        r'(?:Penalty|Fine|Late\s+Fee)[\s:]+',
        re.IGNORECASE
    )

    INTEREST_KEYWORDS: Pattern = re.compile(
        r'(?:Interest)[\s:]+',
        re.IGNORECASE
    )

    # Deadline keywords
    DEADLINE_KEYWORDS: Pattern = re.compile(
        r'(?:within|by|before|on\s+or\s+before|not\s+later\s+than|deadline|due\s+(?:date|on))',
        re.IGNORECASE
    )

    DAYS_PATTERN: Pattern = re.compile(
        r'(\d+)\s*(?:days?|working\s+days?)',
        re.IGNORECASE
    )
