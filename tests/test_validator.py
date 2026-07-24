import pytest

from birthday_sms.validator import is_valid_e164_phone_number, normalize_phone_number


@pytest.mark.parametrize(
    "phone_number,expected",
    [
        ("+919876543210", True),
        ("+14155552671", True),
        ("9876543210", False),          # missing leading +
        ("+91987654321012345", False),  # too long
        ("+91", False),                 # too short
        ("", False),
        ("+91abcde12345", False),
    ],
)
def test_is_valid_e164_phone_number(phone_number, expected):
    assert is_valid_e164_phone_number(phone_number) is expected


def test_normalize_phone_number_strips_separators():
    assert normalize_phone_number(" +91 987-654 (3210) ") == "+919876543210"
