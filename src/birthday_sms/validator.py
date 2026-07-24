"""Input validation helpers."""

from __future__ import annotations

import re

# Simplified E.164 check: a leading '+', then 8-15 digits total.
# This intentionally does not attempt full libphonenumber-grade
# validation - it is a lightweight sanity check appropriate for a
# small classroom-scale contact list.
_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def is_valid_e164_phone_number(phone_number: str) -> bool:
    """Return True if `phone_number` looks like a valid E.164 number.

    Example valid values: "+919876543210", "+14155552671".
    """
    return bool(_E164_PATTERN.match(phone_number.strip()))


def normalize_phone_number(phone_number: str) -> str:
    """Strip whitespace and common separator characters from a phone
    number, leaving the leading '+' and digits only."""
    stripped = phone_number.strip()
    cleaned = re.sub(r"[\s\-().]", "", stripped)
    return cleaned
