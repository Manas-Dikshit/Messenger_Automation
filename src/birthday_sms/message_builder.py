"""Message template engine.

Supports simple `{PLACEHOLDER}` substitution. Deliberately avoids
Python's `str.format()` directly on user-supplied templates, because
a template containing stray `{` / `}` characters (e.g. from a typo)
would raise a `KeyError`/`ValueError` and crash the whole run. Instead
we do a safe, explicit substitution pass.
"""

from __future__ import annotations

from datetime import date

from birthday_sms.constants import (
    PLACEHOLDER_AGE,
    PLACEHOLDER_BRIEF,
    PLACEHOLDER_CLASSIFICATION,
    PLACEHOLDER_FIRST_NAME,
    PLACEHOLDER_NAME,
    PLACEHOLDER_TODAY,
    PLACEHOLDER_YEAR,
)
from birthday_sms.models import Contact


class MessageBuilder:
    """Renders a message template for a given contact and date."""

    def render(self, template: str, contact: Contact, today: date) -> str:
        """Substitute all known placeholders in `template`.

        Unknown placeholders (e.g. a typo'd `{NAEM}`) are left as-is
        in the output rather than raising, so a template mistake never
        blocks the SMS send - it just produces a visibly odd message
        the teacher can notice and fix for next year.
        """
        replacements = {
            PLACEHOLDER_NAME: contact.name,
            PLACEHOLDER_FIRST_NAME: contact.first_name,
            PLACEHOLDER_TODAY: today.isoformat(),
            PLACEHOLDER_YEAR: str(today.year),
            PLACEHOLDER_AGE: str(contact.age_turning(today)),
            PLACEHOLDER_CLASSIFICATION: contact.classification,
            PLACEHOLDER_BRIEF: contact.brief,
        }

        rendered = template
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)
        return rendered
