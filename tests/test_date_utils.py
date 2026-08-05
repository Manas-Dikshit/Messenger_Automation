from datetime import date, datetime

import pytest

import birthday_sms.date_utils as date_utils_module
from birthday_sms.date_utils import (
    parse_date,
    today_in_timezone,
)
from birthday_sms.exceptions import InvalidDateError


class TestParseDate:
    def test_parses_iso_format(self):
        assert parse_date("1999-05-16") == date(1999, 5, 16)

    def test_parses_dd_mm_yyyy(self):
        assert parse_date("16-05-1999") == date(1999, 5, 16)

    def test_parses_dd_slash_mm_slash_yyyy(self):
        assert parse_date("16/05/1999") == date(1999, 5, 16)

    def test_parses_date_with_whitespace(self):
        assert parse_date(" 1999-05-16 ") == date(1999, 5, 16)

    def test_raises_on_empty_string(self):
        with pytest.raises(InvalidDateError):
            parse_date("", row_number=5)

    def test_raises_on_whitespace_only(self):
        with pytest.raises(InvalidDateError):
            parse_date("   ", row_number=5)

    def test_raises_on_garbage_input(self):
        with pytest.raises(InvalidDateError):
            parse_date("not-a-date", row_number=7)

    def test_error_includes_row_number(self):
        with pytest.raises(InvalidDateError) as exc_info:
            parse_date("garbage", row_number=42)

        assert "Row 42" in str(exc_info.value)

    def test_raises_on_invalid_calendar_date(self):
        with pytest.raises(InvalidDateError):
            parse_date("2026-02-30")


class TestTodayInTimezone:
    def test_returns_a_date_for_valid_timezone(self):
        result = today_in_timezone("Asia/Kolkata")
        assert isinstance(result, date)

    def test_raises_on_invalid_timezone(self):
        with pytest.raises(ValueError):
            today_in_timezone("Not/A_Real_Zone")


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(
            2026,
            7,
            26,
            0,
            30,
            0,
            tzinfo=tz,
        )


class TestTodayInTimezoneWithFrozenClock:
    def test_returns_expected_date(self, monkeypatch):
        monkeypatch.setattr(
            date_utils_module,
            "datetime",
            FrozenDateTime,
        )

        assert today_in_timezone("Asia/Kolkata") == date(2026, 7, 26)


class TestNowInTimezone:
    def test_returns_timezone_aware_datetime(self):
        from birthday_sms.date_utils import now_in_timezone

        result = now_in_timezone("Asia/Kolkata")

        assert result.tzinfo is not None

    def test_raises_on_unknown_timezone(self):
        from birthday_sms.date_utils import now_in_timezone

        with pytest.raises(ValueError):
            now_in_timezone("Not/A_Real_Zone")


class TestFormatTimestamp:
    def test_formats_with_timezone_abbreviation(self):
        from zoneinfo import ZoneInfo

        from birthday_sms.date_utils import format_timestamp

        dt = datetime(2026, 8, 5, 14, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

        result = format_timestamp(dt)

        assert result == "2026-08-05 14:30:00 IST"

    def test_none_returns_dash(self):
        from birthday_sms.date_utils import format_timestamp

        assert format_timestamp(None) == "-"
