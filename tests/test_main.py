"""Instant smoke tests for the CLI entrypoint (birthday_sms.main)."""

from __future__ import annotations

import pytest

import birthday_sms.main as main_module


class TestMainConfigurationError:
    def test_returns_1_when_required_secret_missing(self, monkeypatch, capsys):
        monkeypatch.delenv("SMS_GATEWAY_USERNAME", raising=False)
        monkeypatch.delenv("SMS_GATEWAY_PASSWORD", raising=False)

        exit_code = main_module.main()

        assert exit_code == 1
        assert "CONFIGURATION ERROR" in capsys.readouterr().err


class TestMainNoBirthdaysToday:
    def test_returns_0_and_skips_wait_when_no_match(self, monkeypatch, tmp_path):
        csv_path = tmp_path / "birthdays.csv"
        csv_path.write_text("Name,Birthday,PhoneNumber\nAlice,1990-01-01,+10000000000\n")

        monkeypatch.setenv("SMS_GATEWAY_USERNAME", "user")
        monkeypatch.setenv("SMS_GATEWAY_PASSWORD", "pass")
        monkeypatch.setenv("BIRTHDAY_CSV_PATH", str(csv_path))
        monkeypatch.setenv("STATE_FILE_PATH", str(tmp_path / "state.json"))
        monkeypatch.setenv("DRY_RUN", "false")

        called = {"slept": False}
        monkeypatch.setattr(
            main_module.time, "sleep", lambda *_: called.__setitem__("slept", True)
        )

        exit_code = main_module.main()

        assert exit_code == 0
        assert called["slept"] is False
