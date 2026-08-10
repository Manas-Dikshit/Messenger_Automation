"""Domain models for Birthday SMS Automation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


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
    """A single row from the contacts CSV."""

    name: str
    phone_number: str
    birthday: date
    anniversary: Optional[date] = None
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

    @property
    def spouse(self) -> str:
        """Spouse name parsed from Brief field ('Spouse: <name>' prefix)."""
        brief = self.brief.strip()
        if brief.lower().startswith("spouse:"):
            return brief[len("spouse:") :].strip()
        return ""

    def is_birthday_today(self, today: date) -> bool:
        """Compare month/day only - year is irrelevant for a birthday."""
        return (self.birthday.month, self.birthday.day) == (today.month, today.day)

    def is_anniversary_today(self, today: date) -> bool:
        """Compare month/day of anniversary - returns False if no anniversary set."""
        if self.anniversary is None:
            return False
        return (self.anniversary.month, self.anniversary.day) == (today.month, today.day)

    def age_turning(self, today: date) -> int:
        """Age the contact turns on this birthday."""
        return today.year - self.birthday.year


@dataclass(slots=True)
class SendResult:
    """Result of processing one contact for the current run."""

    contact: Contact
    status: SendStatus
    event_type: str = "birthday"  # "birthday" or "anniversary"
    message_id: str | None = None
    error: str | None = None
    rendered_message: str | None = None
    sent_at: str | None = None
    delivered_at: str | None = None
    retry_attempts: int | None = None


@dataclass(slots=True)
class RunMetadata:
    """Context about the run itself, for the step-summary report."""

    trigger_event: str = "unknown"
    trigger_schedule: str | None = None
    dry_run: bool = False
    started_at: str | None = None
    completed_at: str | None = None
    run_url: str | None = None
