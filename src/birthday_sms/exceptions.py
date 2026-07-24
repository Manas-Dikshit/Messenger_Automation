"""Custom exception hierarchy for Birthday SMS Automation.

Using a dedicated exception hierarchy lets calling code distinguish
between configuration problems, data problems, and network problems,
and react appropriately (fail fast vs. retry vs. skip a single row).
"""

from __future__ import annotations


class BirthdaySmsError(Exception):
    """Base class for all errors raised by this project."""


# --------------------------------------------------------------------------
# Configuration errors
# --------------------------------------------------------------------------
class ConfigurationError(BirthdaySmsError):
    """Raised when required configuration/environment variables are missing
    or invalid (e.g. a GitHub Secret was not set)."""


class MissingSecretError(ConfigurationError):
    """Raised when a required secret/environment variable is absent."""

    def __init__(self, variable_name: str) -> None:
        self.variable_name = variable_name
        super().__init__(
            f"Required environment variable '{variable_name}' is not set. "
            "If running in GitHub Actions, confirm the corresponding "
            "repository secret exists and is passed into the workflow env."
        )


# --------------------------------------------------------------------------
# Data / CSV errors
# --------------------------------------------------------------------------
class CsvError(BirthdaySmsError):
    """Base class for CSV-related errors."""


class CsvFileNotFoundError(CsvError):
    """Raised when the configured CSV path does not exist."""


class CsvSchemaError(CsvError):
    """Raised when the CSV is missing required columns."""


class CsvRowError(CsvError):
    """Raised when an individual CSV row cannot be parsed.

    This is intentionally NOT fatal for the whole run - the caller is
    expected to catch this per-row, log it, and continue processing
    the remaining contacts.
    """

    def __init__(self, row_number: int, reason: str) -> None:
        self.row_number = row_number
        self.reason = reason
        super().__init__(f"Row {row_number}: {reason}")


class InvalidPhoneNumberError(CsvRowError):
    """Raised when a phone number fails E.164 validation."""


class InvalidDateError(CsvRowError):
    """Raised when a birthday value cannot be parsed with any supported
    date format."""


# --------------------------------------------------------------------------
# Messaging errors
# --------------------------------------------------------------------------
class MessageBuildError(BirthdaySmsError):
    """Raised when a message template cannot be rendered."""


# --------------------------------------------------------------------------
# Gateway / API errors
# --------------------------------------------------------------------------
class SmsGatewayError(BirthdaySmsError):
    """Base class for SMS Gateway API errors."""


class SmsGatewayAuthenticationError(SmsGatewayError):
    """Raised on HTTP 401/403 - invalid username/password/token."""


class SmsGatewayUnavailableError(SmsGatewayError):
    """Raised when the gateway cannot be reached at all (device offline,
    DNS failure, connection refused, etc.)."""


class SmsGatewayTimeoutError(SmsGatewayError):
    """Raised when a request exceeds the configured timeout."""


class SmsGatewayResponseError(SmsGatewayError):
    """Raised when the gateway returns a malformed or unexpected response
    body that cannot be parsed."""


class RetryExhaustedError(SmsGatewayError):
    """Raised when all retry attempts for a request have been exhausted."""

    def __init__(self, attempts: int, last_error: Exception | None = None) -> None:
        self.attempts = attempts
        self.last_error = last_error
        suffix = f" Last error: {last_error}" if last_error else ""
        super().__init__(f"Gave up after {attempts} attempts.{suffix}")
