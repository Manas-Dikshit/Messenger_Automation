from datetime import date, datetime

import pytest

import birthday_sms.date_utils as date_utils_module
from birthday_sms.date_utils import (
    next_midnight_date,
    parse_date,
    seconds_until_next_midnight,
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

    def test_returns_date_in_requested_timezone(self, monkeypatch):
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

        monkeypatch.setattr(
            date_utils_module,
            "datetime",
            FrozenDateTime,
        )

        assert today_in_timezone("Asia/Kolkata") == date(2026, 7, 26)


class _FrozenDateTime(datetime):
    """A datetime subclass whose .now() always returns a fixed instant."""

    _frozen_at: datetime

    @classmethod
    def now(cls, tz=None):
        return cls._frozen_at.replace(tzinfo=tz) if tz else cls._frozen_at


@pytest.fixture
def freeze_time(monkeypatch):
    """Freeze birthday_sms.date_utils's notion of the current time."""

    def _freeze(naive_dt: datetime) -> None:
        frozen_cls = type(
            "_Frozen",
            (_FrozenDateTime,),
            {"_frozen_at": naive_dt},
        )

        monkeypatch.setattr(
            date_utils_module,
            "datetime",
            frozen_cls,
        )

    return _freeze


class TestNextMidnightDate:
    def test_returns_tomorrow_when_run_at_2350(self, freeze_time):
        freeze_time(datetime(2026, 7, 25, 23, 50, 0))

        assert next_midnight_date("Asia/Kolkata") == date(2026, 7, 26)

    def test_handles_month_rollover(self, freeze_time):
        freeze_time(datetime(2026, 7, 31, 23, 50, 0))

        assert next_midnight_date("Asia/Kolkata") == date(2026, 8, 1)

    def test_handles_year_rollover(self, freeze_time):
        freeze_time(datetime(2026, 12, 31, 23, 50, 0))

        assert next_midnight_date("Asia/Kolkata") == date(2027, 1, 1)

    def test_raises_on_invalid_timezone(self):
        with pytest.raises(ValueError):
            next_midnight_date("Not/A_Real_Zone")


class TestSecondsUntilNextMidnight:
    def test_returns_ten_minutes_when_run_at_2350(self, freeze_time):
        freeze_time(datetime(2026, 7, 25, 23, 50, 0))

        assert seconds_until_next_midnight("Asia/Kolkata") == pytest.approx(
            600.0
        )

    def test_returns_full_day_at_exact_midnight(self, freeze_time):
        freeze_time(datetime(2026, 7, 25, 0, 0, 0))

        assert seconds_until_next_midnight("Asia/Kolkata") == pytest.approx(
            86400.0
        )

    def test_raises_on_invalid_timezone(self):
        with pytest.raises(ValueError):
            seconds_until_next_midnight("Not/A_Real_Zone")