"""CSV loading for contacts.

Implements a simple Repository pattern: `CsvContactRepository` is the
single place that knows how to turn rows on disk into `Contact`
domain objects. Callers never touch `csv.DictReader` directly.

CSV schema (header row required), only birthdays are tracked:

    Name,PhoneNumber,Birthday,Classification,Brief,Address,Enabled,LastSent,MessageTemplate

Only Name, PhoneNumber and Birthday are required. All other columns
are optional and may be blank.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from birthday_sms.constants import (
    CSV_COLUMN_ADDRESS,
    CSV_COLUMN_BIRTHDAY,
    CSV_COLUMN_BRIEF,
    CSV_COLUMN_CLASSIFICATION,
    CSV_COLUMN_ENABLED,
    CSV_COLUMN_LAST_SENT,
    CSV_COLUMN_MESSAGE_TEMPLATE,
    CSV_COLUMN_NAME,
    CSV_COLUMN_PHONE_NUMBER,
    CSV_REQUIRED_COLUMNS,
)
from birthday_sms.date_utils import parse_date
from birthday_sms.exceptions import (
    CsvFileNotFoundError,
    CsvRowError,
    CsvSchemaError,
    InvalidPhoneNumberError,
)
from birthday_sms.models import Contact
from birthday_sms.validator import is_valid_e164_phone_number, normalize_phone_number

logger = logging.getLogger(__name__)


class CsvContactRepository:
    """Reads `Contact` objects out of a CSV file."""

    def __init__(self, csv_path: str | Path) -> None:
        self._csv_path = Path(csv_path)

    def load(self) -> list[Contact]:
        """Load and parse all valid contacts from the CSV file.

        Rows that fail validation are logged and skipped rather than
        aborting the entire run - one bad row should never block
        everyone else's birthday message.

        Returns:
            List of successfully parsed `Contact` objects.

        Raises:
            CsvFileNotFoundError: if the CSV path does not exist.
            CsvSchemaError: if required columns are missing entirely.
        """
        if not self._csv_path.exists():
            raise CsvFileNotFoundError(f"CSV file not found at: {self._csv_path}")

        contacts: list[Contact] = []

        with self._csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            self._validate_schema(reader.fieldnames)

            for row_number, raw_row in enumerate(reader, start=2):  # header is row 1
                try:
                    contact = self._parse_row(raw_row, row_number)
                    contacts.append(contact)
                except CsvRowError as exc:
                    logger.warning("Skipping CSV row due to error: %s", exc)
                    continue

        return contacts

    @staticmethod
    def _validate_schema(fieldnames: list[str] | None) -> None:
        if fieldnames is None:
            raise CsvSchemaError("CSV file appears to be empty (no header row).")

        missing = [col for col in CSV_REQUIRED_COLUMNS if col not in fieldnames]
        if missing:
            raise CsvSchemaError(
                f"CSV is missing required column(s): {', '.join(missing)}. "
                f"Found columns: {', '.join(fieldnames)}"
            )

    @staticmethod
    def _parse_row(raw_row: dict[str, str], row_number: int) -> Contact:
        name = (raw_row.get(CSV_COLUMN_NAME) or "").strip()
        if not name:
            raise CsvRowError(row_number, "Name is required but was empty.")

        raw_phone = (raw_row.get(CSV_COLUMN_PHONE_NUMBER) or "").strip()
        if not raw_phone:
            raise CsvRowError(row_number, "PhoneNumber is required but was empty.")

        phone_number = normalize_phone_number(raw_phone)
        if not is_valid_e164_phone_number(phone_number):
            raise InvalidPhoneNumberError(
                row_number,
                f"Phone number '{raw_phone}' is not valid E.164 " "(expected e.g. +919876543210).",
            )

        raw_birthday = (raw_row.get(CSV_COLUMN_BIRTHDAY) or "").strip()
        birthday = parse_date(raw_birthday, row_number)

        # Blank/missing Enabled means "enabled" (opt-out column, not opt-in):
        # only an explicit falsy value (e.g. FALSE, 0, NO, N) disables a contact.
        enabled_raw = (raw_row.get(CSV_COLUMN_ENABLED) or "").strip().upper()
        enabled = enabled_raw not in {"FALSE", "0", "NO", "N"}

        return Contact(
            name=name,
            phone_number=phone_number,
            birthday=birthday,
            classification=(raw_row.get(CSV_COLUMN_CLASSIFICATION) or "").strip(),
            brief=(raw_row.get(CSV_COLUMN_BRIEF) or "").strip(),
            address=(raw_row.get(CSV_COLUMN_ADDRESS) or "").strip(),
            enabled=enabled,
            last_sent=(raw_row.get(CSV_COLUMN_LAST_SENT) or "").strip(),
            message_template=(raw_row.get(CSV_COLUMN_MESSAGE_TEMPLATE) or "").strip(),
        )
