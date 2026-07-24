"""Date parsing and timezone-aware "today" / "next midnight" resolution."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from birthday_sms.constants import SUPPORTED_DATE_FORMATS
from birthday_sms.exceptions import InvalidDateError


def _resolve_zoneinfo(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Unknown IANA timezone '{timezone_name}'. "
            "Example of a valid value: 'Asia/Kolkata'."
        ) from exc


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
    birthday scheduled to fire at midnight IST could land on the wrong
    UTC calendar day if we naively used `date.today()`.
    """
    tz = _resolve_zoneinfo(timezone_name)
    return datetime.now(tz).date()


def next_midnight_date(timezone_name: str) -> date:
    """Return the calendar date of the *next upcoming* local midnight.

    Used by the "detect at 11:50 PM, send at 12:00 AM" flow: the
    workflow runs shortly before midnight, but the birthday it should
    match against is the day that is about to *begin*, not the day
    that is ending. Called at 23:50 IST, this returns tomorrow's date.
    """
    tz = _resolve_zoneinfo(timezone_name)
    now = datetime.now(tz)
    next_midnight_dt = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return next_midnight_dt.date()


def seconds_until_next_midnight(timezone_name: str) -> float:
    """Return how many seconds remain until the next local midnight.

    Used to sleep from the 11:50 PM detection run until exactly
    00:00 IST before actually sending the SMS.
    """
    tz = _resolve_zoneinfo(timezone_name)
    now = datetime.now(tz)
    next_midnight_dt = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (next_midnight_dt - now).total_seconds()