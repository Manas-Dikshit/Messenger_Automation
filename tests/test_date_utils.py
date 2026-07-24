from datetime import date

import pytest

from birthday_sms.date_utils import parse_date, today_in_timezone
from birthday_sms.exceptions import InvalidDateError


class TestParseDate:
    def test_parses_iso_format(self):
        assert parse_date("1999-05-16") == date(1999, 5, 16)

    def test_parses_dd_mm_yyyy(self):
        assert parse_date("16-05-1999") == date(1999, 5, 16)

    def test_parses_dd_slash_mm_slash_yyyy(self):
        assert parse_date("16/05/1999") == date(1999, 5, 16)

    def test_raises_on_empty_string(self):
        with pytest.raises(InvalidDateError):
            parse_date("", row_number=5)

    def test_raises_on_garbage_input(self):
        with pytest.raises(InvalidDateError):
            parse_date("not-a-date", row_number=7)

    def test_error_includes_row_number(self):
        with pytest.raises(InvalidDateError) as exc_info:
            parse_date("garbage", row_number=42)
        assert "Row 42" in str(exc_info.value)


class TestTodayInTimezone:
    def test_returns_a_date_for_valid_timezone(self):
        result = today_in_timezone("Asia/Kolkata")
        assert isinstance(result, date)

    def test_raises_on_invalid_timezone(self):
        with pytest.raises(ValueError):
            today_in_timezone("Not/A_Real_Zone")
