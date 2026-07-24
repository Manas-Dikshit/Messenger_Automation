"""Configuration loading and validation.

All configuration is sourced from environment variables so that the
exact same code runs unmodified locally (via a `.env` file) and in
GitHub Actions (via repository Secrets injected as env vars). Nothing
is ever hardcoded, and nothing sensitive is ever committed to the
repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from birthday_sms.constants import (
    DEFAULT_API_TIMEOUT_SECONDS,
    DEFAULT_CSV_PATH,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MESSAGE_TEMPLATE,
    DEFAULT_RETRY_BACKOFF_BASE_SECONDS,
    DEFAULT_RETRY_BACKOFF_MAX_SECONDS,
    DEFAULT_SMS_GATEWAY_BASE_URL,
    DEFAULT_TIMEZONE,
    STATE_FILE_PATH,
)
from birthday_sms.exceptions import MissingSecretError


def _get_env(name: str, default: str | None = None, required: bool = False) -> str | None:
    """Read an environment variable with optional default/required check."""
    value = os.environ.get(name, default)
    if required and not value:
        raise MissingSecretError(name)
    return value


def _get_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise MissingSecretError(name) from exc


def _get_env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise MissingSecretError(name) from exc


def _get_env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class SmsGatewayConfig:
    """Connection details for SMS Gateway for Android (Cloud Mode)."""

    base_url: str
    username: str
    password: str
    timeout_seconds: int
    max_retries: int
    retry_backoff_base_seconds: float
    retry_backoff_max_seconds: float
    default_sender_sim: str | None = None


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Top level application configuration."""

    csv_path: str
    timezone: str
    default_message_template: str
    log_level: str
    dry_run: bool
    state_file_path: str
    gateway: SmsGatewayConfig = field(repr=False)

    @staticmethod
    def from_env() -> "AppConfig":
        """Build configuration from environment variables.

        Raises:
            MissingSecretError: if a required credential is absent.
        """
        base_url = _get_env("SMS_GATEWAY_BASE_URL", DEFAULT_SMS_GATEWAY_BASE_URL)
        username = _get_env("SMS_GATEWAY_USERNAME", required=True)
        password = _get_env("SMS_GATEWAY_PASSWORD", required=True)

        gateway = SmsGatewayConfig(
            base_url=(base_url or DEFAULT_SMS_GATEWAY_BASE_URL).rstrip("/"),
            username=username or "",
            password=password or "",
            timeout_seconds=_get_env_int(
                "SMS_GATEWAY_TIMEOUT_SECONDS", DEFAULT_API_TIMEOUT_SECONDS
            ),
            max_retries=_get_env_int("SMS_GATEWAY_MAX_RETRIES", DEFAULT_MAX_RETRIES),
            retry_backoff_base_seconds=_get_env_float(
                "SMS_GATEWAY_RETRY_BACKOFF_BASE", DEFAULT_RETRY_BACKOFF_BASE_SECONDS
            ),
            retry_backoff_max_seconds=_get_env_float(
                "SMS_GATEWAY_RETRY_BACKOFF_MAX", DEFAULT_RETRY_BACKOFF_MAX_SECONDS
            ),
            default_sender_sim=_get_env("SMS_GATEWAY_SENDER_SIM", None),
        )

        return AppConfig(
            csv_path=_get_env("BIRTHDAY_CSV_PATH", DEFAULT_CSV_PATH) or DEFAULT_CSV_PATH,
            timezone=_get_env("BIRTHDAY_TIMEZONE", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE,
            default_message_template=_get_env(
                "DEFAULT_MESSAGE_TEMPLATE", DEFAULT_MESSAGE_TEMPLATE
            )
            or DEFAULT_MESSAGE_TEMPLATE,
            log_level=_get_env("LOG_LEVEL", DEFAULT_LOG_LEVEL) or DEFAULT_LOG_LEVEL,
            dry_run=_get_env_bool("DRY_RUN", False),
            state_file_path=_get_env("STATE_FILE_PATH", STATE_FILE_PATH) or STATE_FILE_PATH,
            gateway=gateway,
        )
