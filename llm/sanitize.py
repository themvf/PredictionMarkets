"""Prompt injection sanitization for external data.

All data flowing from Kalshi/Polymarket APIs into GPT-4o prompts must
pass through this module. External API data is *untrusted input* — a
malicious or compromised market listing could embed instruction-override
payloads in titles, descriptions, or categories.

Defence layers:
1. **Pattern stripping** — removes known injection patterns
   (role-play instructions, system prompt overrides, delimiter attacks)
2. **Length truncation** — prevents context-window flooding
3. **Character filtering** — strips control characters and unusual Unicode
4. **Delimiter escaping** — neutralises structural markers that could
   break out of data sections in prompt templates

Usage:
    from llm.sanitize import sanitize_text, sanitize_market_fields

    clean_title = sanitize_text(raw_title, max_length=200)
    clean_dict = sanitize_market_fields(raw_market_dict)
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional


# ── Length Limits ────────────────────────────────────────────
# Per-field maximums.  Market titles rarely exceed 120 chars;
# descriptions can be longer but should never dominate the prompt.

MAX_LENGTHS: Dict[str, int] = {
    "title": 200,
    "description": 500,
    "category": 100,
    "match_reason": 300,
    "rules_primary": 500,
    "question": 200,
    "default": 300,
}


# ── Injection Patterns ──────────────────────────────────────
# Regex patterns that signal an attempt to override LLM instructions.
# Compiled once at import time for performance.

_INJECTION_PATTERNS = [
    # Role-play / persona hijacks
    re.compile(r"(?i)\b(you\s+are|act\s+as|pretend\s+to\s+be|role[\s-]*play)\b"),
    # System prompt override attempts
    re.compile(r"(?i)(ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts?|context))"),
    re.compile(r"(?i)(disregard\s+(all\s+)?(previous|above|prior))"),
    re.compile(r"(?i)(new\s+instructions?:)"),
    re.compile(r"(?i)(system\s*prompt|<<\s*SYS|<\|system\|>|\[INST\])"),
    # Delimiter injection (trying to break out of data sections)
    re.compile(r"(?i)(---+\s*(end|begin|system|instructions?))"),
    re.compile(r"(?i)(```\s*(system|instructions?|prompt))"),
    # Output manipulation
    re.compile(r"(?i)(respond\s+with|output\s+only|return\s+the\s+following)"),
    re.compile(r"(?i)(do\s+not\s+(mention|reveal|disclose|discuss))"),
    # Encoding evasion (base64 instruction smuggling)
    re.compile(r"(?i)(base64[\s:]+[A-Za-z0-9+/=]{20,})"),
]

# Characters that could be used to break prompt structure
_STRUCTURAL_CHARS = re.compile(r"[{}\[\]<>|\\`~]")


def sanitize_text(text: Optional[str],
                  max_length: int = 300,
                  field_name: str = "default",
                  strip_structural: bool = False) -> Optional[str]:
    """Sanitize a single text field from external API data.

    Args:
        text: Raw string from API response.
        max_length: Max characters to retain (0 = use field default).
        field_name: Used to look up per-field length limits.
        strip_structural: If True, remove braces/brackets/backticks
                         that could break prompt templates.

    Returns:
        Sanitized string, or None if input is None.
    """
    if text is None:
        return None
    if not isinstance(text, str):
        text = str(text)

    # 1. Strip control characters (keep newlines and tabs for readability)
    text = _strip_control_chars(text)

    # 2. Normalise Unicode (NFC) to prevent homoglyph evasion
    text = unicodedata.normalize("NFC", text)

    # 3. Remove known injection patterns
    text = _strip_injection_patterns(text)

    # 4. Optionally strip structural characters
    if strip_structural:
        text = _STRUCTURAL_CHARS.sub("", text)

    # 5. Truncate to max length
    limit = max_length or MAX_LENGTHS.get(field_name, MAX_LENGTHS["default"])
    if len(text) > limit:
        text = text[:limit] + "..."

    # 6. Collapse excess whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def sanitize_market_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize all string fields in a market data dictionary.

    Applies field-specific length limits and injection stripping to
    fields that will flow into prompt templates: title, description,
    category, and any other string fields.

    Non-string fields (prices, volumes, IDs) are passed through unchanged.
    """
    result = dict(data)

    # Fields that flow into prompts and need sanitization
    text_fields = {
        "title": {"max_length": MAX_LENGTHS["title"]},
        "description": {"max_length": MAX_LENGTHS["description"]},
        "category": {"max_length": MAX_LENGTHS["category"]},
        "question": {"max_length": MAX_LENGTHS["question"]},
        "rules_primary": {"max_length": MAX_LENGTHS["rules_primary"]},
        "match_reason": {"max_length": MAX_LENGTHS["match_reason"]},
        "subtitle": {"max_length": MAX_LENGTHS["title"]},
        "groupItemTitle": {"max_length": MAX_LENGTHS["title"]},
    }

    for field, opts in text_fields.items():
        if field in result and isinstance(result[field], str):
            result[field] = sanitize_text(
                result[field],
                max_length=opts["max_length"],
                field_name=field,
            )

    return result


def sanitize_for_prompt(text: Optional[str],
                        max_length: int = 200) -> str:
    """Sanitize text that will be directly interpolated into a prompt.

    Stricter than sanitize_text — also removes structural characters
    that could break prompt template delimiters.

    Returns empty string (not None) for safety in f-strings.
    """
    if text is None:
        return ""
    cleaned = sanitize_text(text, max_length=max_length, strip_structural=True)
    return cleaned or ""


def _strip_control_chars(text: str) -> str:
    """Remove ASCII control characters except newline, tab, carriage return."""
    return "".join(
        ch for ch in text
        if ch in ("\n", "\t", "\r") or (ord(ch) >= 32)
    )


def _strip_injection_patterns(text: str) -> str:
    """Remove substrings matching known injection patterns.

    Replaces matches with '[filtered]' so the data remains readable
    but the injection payload is neutralised.
    """
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub("[filtered]", text)
    return text
