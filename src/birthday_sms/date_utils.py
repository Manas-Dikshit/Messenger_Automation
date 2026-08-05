"""Date parsing and timezone-aware date resolution."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from birthday_sms.constants import SUPPORTED_DATE_FORMATS
from birthday_sms.exceptions import InvalidDateError


def _resolve_zoneinfo(timezone_name: str) -> ZoneInfo:
    """Resolve an IANA timezone name into a ZoneInfo instance."""
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Unknown IANA timezone '{timezone_name}'. " "Example of a valid value: 'Asia/Kolkata'."
        ) from exc


def parse_date(raw_value: str, row_number: int = 0) -> date:
    """Parse a date string using each supported format in turn.

    Args:
        raw_value: The raw string from the CSV, e.g. "1999-05-16".
        row_number: 1-indexed CSV row, used only for error messages.

    Returns:
        A datetime.date.

    Raises:
        InvalidDateError: If no supported format matches.
    """
    value = raw_value.strip()

    if not value:
        raise InvalidDateError(
            row_number,
            "Birthday value is empty.",
        )

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


def now_in_timezone(timezone_name: str) -> datetime:
    """Return the current timezone-aware datetime in the given IANA timezone."""
    tz = _resolve_zoneinfo(timezone_name)
    return datetime.now(tz)


def format_timestamp(dt: datetime | None) -> str:
    """Render a timestamp for display, e.g. '2026-08-05 14:30:00 IST'."""
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def today_in_timezone(timezone_name: str) -> date:
    """Return today's calendar date in the given IANA timezone.

    GitHub Actions runners use UTC, so the application must resolve
    the current date using the configured local timezone.
    """
    tz = _resolve_zoneinfo(timezone_name)
    return datetime.now(tz).date()


def next_midnight_date(timezone_name: str) -> date:
    """Return the calendar date of the next local midnight.

    This function is retained for compatibility with the previous
    pre-midnight workflow and its tests.

    The current production workflow should use today_in_timezone()
    instead and run shortly after midnight.
    """
    tz = _resolve_zoneinfo(timezone_name)
    now = datetime.now(tz)

    next_midnight_dt = (now + timedelta(days=1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    return next_midnight_dt.date()


def seconds_until_next_midnight(timezone_name: str) -> float:
    """Return the number of seconds until the next local midnight.

    This function is retained for compatibility with the previous
    pre-midnight workflow and its tests.
    """
    tz = _resolve_zoneinfo(timezone_name)
    now = datetime.now(tz)

    next_midnight_dt = (now + timedelta(days=1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    return (next_midnight_dt - now).total_seconds()
