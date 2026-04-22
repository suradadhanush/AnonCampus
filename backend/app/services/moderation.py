"""
Moderation service — 4-layer pipeline

Fix applied: alphanumeric patterns like CS21B123 / 25NU1A4430
are STUDENT IDs — they must NOT be blocked or redacted.
Only true PII (emails, phone numbers, name+title combos) is redacted.
"""
import re
from typing import List, Tuple

# ── PII patterns ──────────────────────────────────────────────────────────────

PII_PATTERNS = [
    (re.compile(r'\b[\w.+-]+@[\w-]+\.\w+\b'), "EMAIL"),
    (re.compile(r'\b(\+91|0)?[6-9]\d{9}\b'), "PHONE"),
    # Aadhaar-style 12-digit numbers
    (re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'), "ID_NUMBER"),
]

# Direct accusations: title + name (NOT bare alphanumeric IDs)
ACCUSATION_PATTERNS = [
    re.compile(r'\b(professor|teacher|sir|ma\'am|mam|mr\.|ms\.|dr\.)\s+[A-Z][a-z]+(?: [A-Z][a-z]+)?\b',
               re.IGNORECASE),
    re.compile(r'\b(HOD|principal|director|dean)\s+[A-Z][a-z]+\b', re.IGNORECASE),
    # Full name pattern: two capitalized words not preceded by a student-ID context
    re.compile(r'(?<![A-Z0-9])([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})(?!\s*[A-Z0-9])', re.UNICODE),
]

# NOTE: We deliberately do NOT block patterns like:
#   CS21B123, 25NU1A4430, ECE2022001
# These are student IDs / roll numbers — valid in grievance context.
# Rule: only block when combined with personally identifying title/name.

PROFANITY_SET: set = set()  # Populate from DB/config in production

MIN_BODY = 20
MAX_BODY = 5000
MIN_TITLE = 10
MAX_TITLE = 500


def moderate_text(title: str, body: str) -> Tuple[bool, List[str], str, str]:
    """
    Returns (is_clean, flags, cleaned_title, cleaned_body).
    is_clean=False only for hard blocking flags (too_short, too_long).
    PII/accusation flags are informational — content is auto-redacted but not blocked.
    """
    flags: List[str] = []
    cleaned_title = title.strip()
    cleaned_body = body.strip()

    # Layer 1: PII detection and redaction
    for pattern, pii_type in PII_PATTERNS:
        if pattern.search(cleaned_title):
            flags.append(f"pii:{pii_type.lower()}")
            cleaned_title = pattern.sub(f"[{pii_type} REDACTED]", cleaned_title)
        if pattern.search(cleaned_body):
            if f"pii:{pii_type.lower()}" not in flags:
                flags.append(f"pii:{pii_type.lower()}")
            cleaned_body = pattern.sub(f"[{pii_type} REDACTED]", cleaned_body)

    # Layer 2: Accusation detection (title + name combos only)
    for pattern in ACCUSATION_PATTERNS:
        if pattern.search(cleaned_body):
            flags.append("accusation:name_detected")
            cleaned_body = pattern.sub("[NAME REDACTED]", cleaned_body)
        if pattern.search(cleaned_title):
            if "accusation:name_detected" not in flags:
                flags.append("accusation:name_detected")
            cleaned_title = pattern.sub("[NAME REDACTED]", cleaned_title)

    # Layer 3: Profanity
    if PROFANITY_SET:
        words = set(cleaned_body.lower().split())
        found = words & PROFANITY_SET
        if found:
            flags.append("profanity")
            for word in found:
                cleaned_body = re.sub(
                    r'\b' + re.escape(word) + r'\b',
                    '[REMOVED]',
                    cleaned_body,
                    flags=re.IGNORECASE,
                )

    # Layer 4: Length validation (hard blocks)
    if len(cleaned_body.strip()) < MIN_BODY:
        flags.append("too_short")
    if len(cleaned_body) > MAX_BODY:
        flags.append("too_long")
        cleaned_body = cleaned_body[:MAX_BODY]
    if len(cleaned_title.strip()) < MIN_TITLE:
        flags.append("title_too_short")
    if len(cleaned_title) > MAX_TITLE:
        flags.append("title_too_long")
        cleaned_title = cleaned_title[:MAX_TITLE]

    blocking = {"too_short", "too_long", "title_too_short", "title_too_long"}
    is_clean = not any(f in blocking for f in flags)

    return is_clean, flags, cleaned_title, cleaned_body
