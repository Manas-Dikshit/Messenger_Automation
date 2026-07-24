"""Date parsing and timezone-aware "today" resolution."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from birthday_sms.constants import SUPPORTED_DATE_FORMATS
from birthday_sms.exceptions import InvalidDateError


def parse_date(raw_value: str, row_number: int = 0) -> date:
    """Parse a date string using each supported format in turn.

    Args:
        raw_value: The raw string from the CSV, e.g. "1999-05-16".
        row_number: 1-indexed CSV row, used only for error messages.

    Returns:
        A `datetime.date`.

    Raises:
        InvalidDateError: if no supported format matches.
    """
    value = raw_value.strip()
    if not value:
        raise InvalidDateError(row_number, "Birthday value is empty.")

    for fmt in SUPPORTED_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise InvalidDateError(
        row_number,
        f"Could not parse birthday '{raw_value}'. "
        f"Supported formats: {', '.join(SUPPORTED_DATE_FORMATS)}",
    )


def today_in_timezone(timezone_name: str) -> date:
    """Return "today" as observed in the given IANA timezone.

    This matters because GitHub Actions runners execute in UTC. A
    birthday scheduled to fire at 08:00 IST could land on the wrong
    UTC calendar day if we naively used `date.today()`.
    """
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Unknown IANA timezone '{timezone_name}'. "
            "Example of a valid value: 'Asia/Kolkata'."
        ) from exc
    return datetime.now(tz).date()
