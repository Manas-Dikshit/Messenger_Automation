import pytest

from birthday_sms.config import AppConfig
from birthday_sms.exceptions import MissingSecretError


class TestAppConfig:
    def test_raises_when_username_missing(self, monkeypatch):
        monkeypatch.delenv("SMS_GATEWAY_USERNAME", raising=False)
        monkeypatch.setenv("SMS_GATEWAY_PASSWORD", "pass")

        with pytest.raises(MissingSecretError):
            AppConfig.from_env()

    def test_raises_when_password_missing(self, monkeypatch):
        monkeypatch.setenv("SMS_GATEWAY_USERNAME", "user")
        monkeypatch.delenv("SMS_GATEWAY_PASSWORD", raising=False)

        with pytest.raises(MissingSecretError):
            AppConfig.from_env()

    def test_loads_successfully_with_required_vars(self, monkeypatch):
        monkeypatch.setenv("SMS_GATEWAY_USERNAME", "user")
        monkeypatch.setenv("SMS_GATEWAY_PASSWORD", "pass")

        config = AppConfig.from_env()

        assert config.gateway.username == "user"
        assert config.gateway.password == "pass"
        assert config.csv_path  # has a sensible default
        assert config.timezone  # has a sensible default

    def test_applies_overrides_from_env(self, monkeypatch):
        monkeypatch.setenv("SMS_GATEWAY_USERNAME", "user")
        monkeypatch.setenv("SMS_GATEWAY_PASSWORD", "pass")
        monkeypatch.setenv("BIRTHDAY_TIMEZONE", "America/New_York")
        monkeypatch.setenv("DRY_RUN", "true")
        monkeypatch.setenv("SMS_GATEWAY_MAX_RETRIES", "7")

        config = AppConfig.from_env()

        assert config.timezone == "America/New_York"
        assert config.dry_run is True
        assert config.gateway.max_retries == 7
