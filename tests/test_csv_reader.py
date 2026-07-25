from pathlib import Path

import pytest

from birthday_sms.csv_reader import CsvContactRepository
from birthday_sms.exceptions import CsvFileNotFoundError, CsvSchemaError

VALID_CSV = (
    "Name,PhoneNumber,Birthday,Classification,Brief,Address,"
    "Enabled,LastSent,MessageTemplate\n"
    "Rahul Sharma,+919876543210,1999-05-16,Student,Class 10,Kolkata,TRUE,,\n"
    "Ananya Verma,+919812345678,2005-07-25,Student,Class 9,Kolkata,FALSE,,\n"
)

MISSING_COLUMN_CSV = (
    "Name,Birthday\n"
    "Rahul Sharma,1999-05-16\n"
)

BAD_ROW_CSV = (
    "Name,PhoneNumber,Birthday\n"
    "Rahul Sharma,+919876543210,1999-05-16\n"
    ",+919812345678,2005-07-25\n"
    "Bad Phone Guy,not-a-phone,2005-07-25\n"
    "Bad Date Guy,+919900000000,not-a-date\n"
)


def write_csv(tmp_path: Path, content: str) -> Path:
    csv_path = tmp_path / "birthdays.csv"
    csv_path.write_text(content, encoding="utf-8")
    return csv_path


class TestCsvContactRepository:
    def test_loads_valid_contacts(self, tmp_path):
        csv_path = write_csv(tmp_path, VALID_CSV)
        repo = CsvContactRepository(csv_path)

        contacts = repo.load()

        assert len(contacts) == 2
        assert contacts[0].name == "Rahul Sharma"
        assert contacts[0].enabled is True
        assert contacts[1].enabled is False

    def test_raises_when_file_missing(self, tmp_path):
        repo = CsvContactRepository(tmp_path / "does_not_exist.csv")

        with pytest.raises(CsvFileNotFoundError):
            repo.load()

    def test_raises_on_missing_required_columns(self, tmp_path):
        csv_path = write_csv(tmp_path, MISSING_COLUMN_CSV)
        repo = CsvContactRepository(csv_path)

        with pytest.raises(CsvSchemaError):
            repo.load()

    def test_skips_bad_rows_but_keeps_good_ones(self, tmp_path):
        csv_path = write_csv(tmp_path, BAD_ROW_CSV)
        repo = CsvContactRepository(csv_path)

        contacts = repo.load()

        # Only the first row is valid; empty name, bad phone, bad date
        # rows should all be skipped with a warning, not raise.
        assert len(contacts) == 1
        assert contacts[0].name == "Rahul Sharma"