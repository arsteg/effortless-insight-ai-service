"""
Hallucination detector for LLM outputs
"""

import re
from typing import List, Dict, Any, Set
import structlog

logger = structlog.get_logger()


class HallucinationDetector:
    """
    Detect potential hallucinations in LLM output

    Checks for:
    - Information not present in source text
    - Made-up section references
    - Fabricated dates/amounts
    - Invented notice numbers
    """

    def __init__(self):
        # Words that might indicate fabricated content
        self.fabrication_indicators = [
            "typically", "usually", "generally", "often",
            "might be", "could be", "may have",
            "it appears", "it seems", "likely",
        ]

        # Common valid prefixes for notice numbers
        self.valid_notice_prefixes = [
            "DRC", "ASMT", "REG", "RET", "GST", "ADT",
            "APL", "PMT", "RFD", "INS", "MIS",
        ]

    def detect_hallucinations(
        self,
        original_text: str,
        llm_output: Dict[str, Any],
    ) -> List[str]:
        """
        Detect potential hallucinations in LLM output

        Args:
            original_text: Original OCR text
            llm_output: LLM analysis output

        Returns:
            List of fields that may contain hallucinations
        """
        potential_hallucinations = []

        # Check metadata fields
        metadata = llm_output.get("metadata", {})

        # Check notice number
        if metadata.get("notice_number"):
            if not self._verify_notice_number(original_text, metadata["notice_number"]):
                potential_hallucinations.append("notice_number")

        # Check GSTIN
        if metadata.get("gstin"):
            if not self._verify_gstin_in_text(original_text, metadata["gstin"]):
                potential_hallucinations.append("gstin")

        # Check amounts are in text
        for field in ["tax_amount", "penalty_amount", "interest_amount"]:
            if metadata.get(field):
                if not self._verify_amount_in_text(original_text, metadata[field]):
                    potential_hallucinations.append(field)

        # Check authority name
        if metadata.get("issuing_authority"):
            if not self._verify_text_fragment(original_text, metadata["issuing_authority"]):
                potential_hallucinations.append("issuing_authority")

        # Check summaries for fabricated content
        if llm_output.get("summary_en"):
            issues = self._check_summary_for_fabrication(
                original_text, llm_output["summary_en"]
            )
            if issues:
                potential_hallucinations.append("summary_en")

        # Check action items for unsubstantiated claims
        for i, item in enumerate(llm_output.get("action_items", [])):
            if not self._verify_action_item(original_text, item):
                potential_hallucinations.append(f"action_items[{i}]")

        # Check legal references
        for i, ref in enumerate(llm_output.get("legal_references", [])):
            if not self._verify_legal_reference(original_text, ref):
                potential_hallucinations.append(f"legal_references[{i}]")

        logger.info(
            "Hallucination detection complete",
            potential_hallucinations=len(potential_hallucinations)
        )

        return potential_hallucinations

    def _verify_notice_number(self, text: str, notice_number: str) -> bool:
        """Verify notice number exists in text"""
        # Clean and check
        notice_clean = notice_number.strip()
        text_upper = text.upper()

        # Direct match
        if notice_clean.upper() in text_upper:
            return True

        # Partial match (at least significant portion)
        parts = re.split(r'[/\-\s]', notice_clean)
        significant_parts = [p for p in parts if len(p) > 3]

        if significant_parts:
            matches = sum(1 for p in significant_parts if p.upper() in text_upper)
            return matches >= len(significant_parts) * 0.5

        return False

    def _verify_gstin_in_text(self, text: str, gstin: str) -> bool:
        """Verify GSTIN exists in text"""
        gstin_clean = gstin.strip().upper()
        return gstin_clean in text.upper()

    def _verify_amount_in_text(self, text: str, amount: float) -> bool:
        """Verify amount exists in text (with various formats)"""
        # Try different format representations
        amount_formats = [
            str(int(amount)),
            f"{amount:.2f}",
            f"{amount:,.2f}",
            self._format_indian_number(int(amount)),
        ]

        text_clean = text.replace(" ", "").replace(",", "")

        for fmt in amount_formats:
            fmt_clean = fmt.replace(",", "")
            if fmt_clean in text_clean:
                return True

        # Check for approximate match (could have OCR errors)
        # Look for numbers close to the amount
        numbers_in_text = re.findall(r'[\d,]+(?:\.\d{2})?', text)
        for num_str in numbers_in_text:
            try:
                num = float(num_str.replace(',', ''))
                if abs(num - amount) / max(amount, 1) < 0.05:  # 5% tolerance
                    return True
            except ValueError:
                continue

        return False

    def _format_indian_number(self, num: int) -> str:
        """Format number in Indian notation"""
        s = str(num)
        if len(s) <= 3:
            return s
        result = s[-3:]
        s = s[:-3]
        while s:
            result = s[-2:] + "," + result
            s = s[:-2]
        return result

    def _verify_text_fragment(self, text: str, fragment: str, min_words: int = 2) -> bool:
        """Verify that significant words from fragment exist in text"""
        words = re.findall(r'\b\w+\b', fragment.lower())
        # Filter out common words
        significant_words = [
            w for w in words
            if len(w) > 3 and w not in {'the', 'and', 'for', 'with', 'from', 'that', 'this'}
        ]

        if not significant_words:
            return True  # Can't verify, assume OK

        text_lower = text.lower()
        matches = sum(1 for w in significant_words if w in text_lower)

        return matches >= min(min_words, len(significant_words))

    def _check_summary_for_fabrication(self, text: str, summary: str) -> List[str]:
        """Check summary for indicators of fabricated content"""
        issues = []
        summary_lower = summary.lower()

        # Check for hedging language that might indicate uncertainty/fabrication
        for indicator in self.fabrication_indicators:
            if indicator in summary_lower:
                issues.append(f"Contains uncertain language: '{indicator}'")

        return issues

    def _verify_action_item(self, text: str, item: Dict[str, Any]) -> bool:
        """Verify action item is substantiated by text"""
        action = item.get("action", "")
        description = item.get("description", "")

        # Combined text to verify
        combined = f"{action} {description}"

        return self._verify_text_fragment(text, combined, min_words=1)

    def _verify_legal_reference(self, text: str, ref: Dict[str, Any]) -> bool:
        """Verify legal reference exists in text"""
        section = ref.get("section", "")

        # The section reference should appear in the original text
        # Extract the key part (e.g., "Section 73" from "Section 73(1)")
        match = re.search(r'(?:Section|Rule)\s*\d+', section, re.IGNORECASE)
        if match:
            key_ref = match.group(0)
            if key_ref.lower() not in text.lower():
                return False

        return True

    def get_confidence_penalty(self, hallucinations: List[str]) -> int:
        """
        Calculate confidence penalty based on hallucinations

        Args:
            hallucinations: List of potentially hallucinated fields

        Returns:
            Penalty to subtract from confidence (0-50)
        """
        if not hallucinations:
            return 0

        # Weight by severity
        critical_fields = {"gstin", "notice_number", "tax_amount", "response_deadline"}
        important_fields = {"penalty_amount", "interest_amount", "issuing_authority"}

        penalty = 0
        for field in hallucinations:
            field_base = field.split("[")[0]  # Handle indexed fields

            if field_base in critical_fields:
                penalty += 15
            elif field_base in important_fields:
                penalty += 10
            elif field_base.startswith("action_items"):
                penalty += 5
            elif field_base.startswith("legal_references"):
                penalty += 5
            else:
                penalty += 3

        return min(50, penalty)
