"""Domain models for Birthday SMS Automation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class SendStatus(str, Enum):
    """Outcome of attempting to send a single SMS."""

    SENT = "SENT"
    SKIPPED_NOT_TODAY = "SKIPPED_NOT_TODAY"
    SKIPPED_DISABLED = "SKIPPED_DISABLED"
    SKIPPED_ALREADY_SENT = "SKIPPED_ALREADY_SENT"
    FAILED = "FAILED"
    DRY_RUN = "DRY_RUN"


@dataclass(slots=True)
class Contact:
    """A single row from the contacts CSV.

    Only the birthday is used for triggering messages - there is no
    anniversary/wedding-day concept in this dataset by design.
    """

    name: str
    phone_number: str
    birthday: date
    classification: str = ""
    brief: str = ""
    address: str = ""
    enabled: bool = True
    last_sent: str = ""
    message_template: str = ""

    @property
    def first_name(self) -> str:
        """Best-effort first name, used for the {FIRST_NAME} placeholder."""
        return self.name.strip().split(" ")[0] if self.name.strip() else self.name

    def is_birthday_today(self, today: date) -> bool:
        """Compare month/day only - year is irrelevant for a birthday."""
        return (self.birthday.month, self.birthday.day) == (today.month, today.day)

    def age_turning(self, today: date) -> int:
        """Age the contact turns on this birthday."""
        return today.year - self.birthday.year


@dataclass(slots=True)
class SendResult:
    """Result of processing one contact for the current run."""

    contact: Contact
    status: SendStatus
    message_id: str | None = None
    error: str | None = None
    rendered_message: str | None = None
