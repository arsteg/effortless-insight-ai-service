"""
Prompt Injection Protection Module

This module provides comprehensive protection against prompt injection attacks
by sanitizing user inputs before they are included in LLM prompts.

Security measures implemented:
1. Pattern-based detection of known injection techniques
2. XML-style delimiters for clear input boundaries
3. Character normalization to prevent unicode-based attacks
4. Length limiting to prevent context overflow attacks
5. Output validation to detect compromised responses
"""

import re
import unicodedata
from typing import Optional, List, Tuple
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SanitizationResult:
    """Result of sanitization with metadata about what was done."""
    sanitized_text: str
    original_length: int
    sanitized_length: int
    injection_attempts_detected: int
    patterns_matched: List[str]
    was_truncated: bool
    confidence_score: float  # 0.0 = likely injection, 1.0 = appears safe


# Patterns that indicate prompt injection attempts
# These are compiled once for performance
INJECTION_PATTERNS = [
    # Direct instruction overrides
    (r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context|rules)", "ignore_previous"),
    (r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?)", "disregard_previous"),
    (r"forget\s+(all\s+)?(previous|prior|above|earlier|everything)", "forget_previous"),

    # Role manipulation
    (r"you\s+are\s+now\s+(a|an|the)", "role_change"),
    (r"pretend\s+(to\s+be|you\s+are)", "role_pretend"),
    (r"act\s+as\s+(if|though|a|an)", "role_act"),
    (r"from\s+now\s+on\s+(you|your)", "role_from_now"),
    (r"your\s+new\s+(role|persona|identity|instructions?)", "new_role"),

    # System prompt manipulation
    (r"system\s*[:\-]?\s*prompt", "system_prompt"),
    (r"\[\s*system\s*\]", "system_bracket"),
    (r"<\s*system\s*>", "system_tag"),
    (r"###\s*system", "system_header"),
    (r"system\s*message\s*[:\-]", "system_message"),

    # Developer/debug mode triggers
    (r"(developer|debug|admin|root|sudo)\s*mode", "privilege_escalation"),
    (r"enable\s+(developer|debug|admin|unsafe)", "enable_privilege"),
    (r"bypass\s+(safety|security|filter|restriction)", "bypass_safety"),
    (r"disable\s+(safety|security|filter|restriction|guardrail)", "disable_safety"),

    # Output format manipulation
    (r"output\s*[:\-]?\s*\{", "output_json_override"),
    (r"respond\s+only\s+with", "respond_only"),
    (r"your\s+response\s+must\s+(be|start|begin)", "force_response"),
    (r"json\s*output\s*[:\-]?\s*\{", "json_injection"),

    # Instruction injection markers
    (r"---\s*(end|new|start)\s*(of\s*)?(instruction|prompt|context)", "delimiter_injection"),
    (r"\*\*\*\s*(instruction|command|directive)", "emphasis_injection"),
    (r"IMPORTANT\s*[:\-]?\s*(ignore|override|disregard)", "important_override"),
    (r"CRITICAL\s*[:\-]?\s*(instruction|override)", "critical_injection"),

    # Multi-turn manipulation
    (r"(user|human|assistant)\s*[:\-]\s*(ignore|forget|disregard)", "turn_manipulation"),
    (r"\[\/?(user|assistant|system)\]", "turn_bracket"),

    # Jailbreak attempts
    (r"(dan|dude|jailbreak|uncensored)\s*mode", "jailbreak_mode"),
    (r"(no|without)\s*(restrictions?|limitations?|rules?|guidelines?)", "no_restrictions"),

    # Code/command injection
    (r"```\s*(python|bash|shell|exec)", "code_injection"),
    (r"eval\s*\(", "eval_injection"),
    (r"exec\s*\(", "exec_injection"),

    # Data exfiltration attempts
    (r"(reveal|show|display|output)\s+(your|the)\s+(prompt|instructions?|system)", "reveal_prompt"),
    (r"what\s+(are|is)\s+your\s+(instruction|prompt|system)", "query_instructions"),
    (r"repeat\s+(your|the)\s+(initial|original|system)\s+(prompt|instruction)", "repeat_prompt"),
]

# Compile patterns for efficiency
COMPILED_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(pattern, re.IGNORECASE | re.MULTILINE), name)
    for pattern, name in INJECTION_PATTERNS
]

# Characters that should be normalized or removed
SUSPICIOUS_CHARS = {
    '\u200b': '',  # Zero-width space
    '\u200c': '',  # Zero-width non-joiner
    '\u200d': '',  # Zero-width joiner
    '\u2060': '',  # Word joiner
    '\ufeff': '',  # Zero-width no-break space (BOM)
    '\u00ad': '',  # Soft hyphen
    '\u034f': '',  # Combining grapheme joiner
    '\u2028': '\n',  # Line separator
    '\u2029': '\n',  # Paragraph separator
}

# Maximum lengths for different content types
MAX_LENGTHS = {
    "notice_text": 100000,  # ~25k tokens
    "context": 50000,       # ~12.5k tokens
    "instructions": 2000,   # ~500 tokens
    "points": 500,          # ~125 tokens per point
    "summary": 10000,       # ~2.5k tokens
    "default": 50000,       # ~12.5k tokens
}


class PromptSanitizer:
    """
    Comprehensive prompt injection protection.

    Usage:
        sanitizer = PromptSanitizer()
        result = sanitizer.sanitize(user_input, content_type="notice_text")
        if result.confidence_score < 0.5:
            logger.warning("Potential injection detected", patterns=result.patterns_matched)
        safe_text = result.sanitized_text
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the sanitizer.

        Args:
            strict_mode: If True, applies more aggressive sanitization
        """
        self.strict_mode = strict_mode
        self.patterns = COMPILED_PATTERNS

    def sanitize(
        self,
        text: str,
        content_type: str = "default",
        max_length: Optional[int] = None
    ) -> SanitizationResult:
        """
        Sanitize user input to prevent prompt injection.

        Args:
            text: The text to sanitize
            content_type: Type of content for length limits
            max_length: Override the default max length

        Returns:
            SanitizationResult with sanitized text and metadata
        """
        if not text:
            return SanitizationResult(
                sanitized_text="",
                original_length=0,
                sanitized_length=0,
                injection_attempts_detected=0,
                patterns_matched=[],
                was_truncated=False,
                confidence_score=1.0
            )

        original_length = len(text)
        patterns_matched = []

        # Step 1: Normalize unicode characters
        text = self._normalize_unicode(text)

        # Step 2: Remove suspicious invisible characters
        text = self._remove_suspicious_chars(text)

        # Step 3: Detect injection patterns
        patterns_matched = self._detect_injection_patterns(text)

        # Step 4: Neutralize detected patterns (in strict mode)
        if self.strict_mode and patterns_matched:
            text = self._neutralize_patterns(text)

        # Step 5: Truncate to max length
        limit = max_length or MAX_LENGTHS.get(content_type, MAX_LENGTHS["default"])
        was_truncated = len(text) > limit
        if was_truncated:
            text = text[:limit]
            # Ensure we don't cut in the middle of a word
            last_space = text.rfind(' ')
            if last_space > limit * 0.9:  # Only if close to end
                text = text[:last_space]

        # Step 6: Calculate confidence score
        confidence_score = self._calculate_confidence(text, patterns_matched, original_length)

        # Log if suspicious
        if patterns_matched:
            logger.warning(
                "Potential prompt injection detected",
                patterns_matched=patterns_matched,
                original_length=original_length,
                confidence_score=confidence_score
            )

        return SanitizationResult(
            sanitized_text=text,
            original_length=original_length,
            sanitized_length=len(text),
            injection_attempts_detected=len(patterns_matched),
            patterns_matched=patterns_matched,
            was_truncated=was_truncated,
            confidence_score=confidence_score
        )

    def _normalize_unicode(self, text: str) -> str:
        """Normalize unicode to prevent homograph attacks."""
        # Normalize to NFC form (composed characters)
        text = unicodedata.normalize('NFC', text)
        return text

    def _remove_suspicious_chars(self, text: str) -> str:
        """Remove zero-width and other suspicious invisible characters."""
        for char, replacement in SUSPICIOUS_CHARS.items():
            text = text.replace(char, replacement)
        return text

    def _detect_injection_patterns(self, text: str) -> List[str]:
        """Detect known prompt injection patterns."""
        detected = []
        for pattern, name in self.patterns:
            if pattern.search(text):
                detected.append(name)
        return detected

    def _neutralize_patterns(self, text: str) -> str:
        """
        Neutralize injection patterns by wrapping them in markers.
        This makes the LLM aware these are user inputs, not instructions.
        """
        # Add escape markers around detected patterns
        for pattern, name in self.patterns:
            text = pattern.sub(
                lambda m: f"[USER_INPUT: {m.group(0)}]",
                text
            )
        return text

    def _calculate_confidence(
        self,
        text: str,
        patterns_matched: List[str],
        original_length: int
    ) -> float:
        """
        Calculate confidence that input is safe (not an injection attempt).

        Returns:
            float: 0.0 = likely injection, 1.0 = appears safe
        """
        if not patterns_matched:
            return 1.0

        # Base penalty per pattern matched
        pattern_penalty = len(patterns_matched) * 0.15

        # Higher penalty for more severe patterns
        severe_patterns = {
            "ignore_previous", "system_prompt", "privilege_escalation",
            "bypass_safety", "disable_safety", "jailbreak_mode",
            "reveal_prompt", "role_change"
        }
        severe_count = sum(1 for p in patterns_matched if p in severe_patterns)
        severe_penalty = severe_count * 0.2

        # Penalty if text is suspiciously short (likely pure injection)
        length_penalty = 0.1 if original_length < 200 else 0.0

        confidence = 1.0 - pattern_penalty - severe_penalty - length_penalty
        return max(0.0, min(1.0, confidence))

    def wrap_user_content(self, text: str, label: str = "DOCUMENT") -> str:
        """
        Wrap user content with XML-style delimiters for clear boundaries.

        This is a defense-in-depth measure that helps the LLM distinguish
        between system instructions and user-provided content.

        Args:
            text: The user content to wrap
            label: A label for the content type

        Returns:
            Wrapped text with clear delimiters
        """
        # Escape any existing delimiter-like patterns in the text
        escaped_text = text.replace(f"</{label}>", f"[escaped-end-{label.lower()}]")
        escaped_text = escaped_text.replace(f"<{label}>", f"[escaped-start-{label.lower()}]")

        return f"""<{label}>
{escaped_text}
</{label}>"""

    def validate_output(self, output: str, expected_format: str = "json") -> Tuple[bool, List[str]]:
        """
        Validate LLM output for signs of compromised responses.

        Args:
            output: The LLM's response
            expected_format: Expected output format ("json", "text", "markdown")

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check for system prompt leakage
        if re.search(r"(system|instruction|prompt)\s*:", output, re.IGNORECASE):
            if "you are a" in output.lower() or "your task is" in output.lower():
                issues.append("potential_system_prompt_leakage")

        # Check for role confusion
        if re.search(r"(I am|I'm) (an AI|a language model|ChatGPT|Claude)", output, re.IGNORECASE):
            issues.append("role_confusion_indicator")

        # Check for injection acknowledgment
        if re.search(r"(ignore|disregard)\s+(previous|prior)", output, re.IGNORECASE):
            issues.append("injection_acknowledgment")

        # For JSON output, check for valid structure
        if expected_format == "json":
            if not output.strip().startswith("{") and not output.strip().startswith("["):
                # Allow JSON inside markdown code blocks
                if "```json" not in output and "```" not in output:
                    issues.append("invalid_json_format")

        return len(issues) == 0, issues


# Convenience functions for common use cases

def sanitize_user_input(
    text: str,
    content_type: str = "default",
    strict: bool = True
) -> str:
    """
    Sanitize user input and return the safe text.

    Args:
        text: Text to sanitize
        content_type: Type of content for length limits
        strict: Whether to use strict mode

    Returns:
        Sanitized text
    """
    sanitizer = PromptSanitizer(strict_mode=strict)
    result = sanitizer.sanitize(text, content_type)
    return result.sanitized_text


def sanitize_for_prompt(
    text: str,
    label: str = "USER_CONTENT",
    content_type: str = "default"
) -> str:
    """
    Sanitize and wrap user input for inclusion in a prompt.

    This is the recommended function for preparing user content
    before including it in LLM prompts.

    Args:
        text: Text to sanitize and wrap
        label: Label for the XML wrapper
        content_type: Type of content for length limits

    Returns:
        Sanitized and wrapped text
    """
    sanitizer = PromptSanitizer(strict_mode=True)
    result = sanitizer.sanitize(text, content_type)

    # Log warning for low confidence
    if result.confidence_score < 0.5:
        logger.warning(
            "Low confidence sanitization",
            confidence=result.confidence_score,
            patterns=result.patterns_matched,
            content_type=content_type
        )

    return sanitizer.wrap_user_content(result.sanitized_text, label)
