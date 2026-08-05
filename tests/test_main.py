"""Instant smoke tests for the CLI entrypoint (birthday_sms.main)."""

from __future__ import annotations

import birthday_sms.main as main_module


class TestMainConfigurationError:
    def test_returns_1_when_required_secret_missing(self, monkeypatch, capsys):
        monkeypatch.delenv("SMS_GATEWAY_USERNAME", raising=False)
        monkeypatch.delenv("SMS_GATEWAY_PASSWORD", raising=False)

        exit_code = main_module.main()

        assert exit_code == 1
        assert "CONFIGURATION ERROR" in capsys.readouterr().err


class TestMainNoBirthdaysToday:
    def test_returns_0_when_no_match(self, monkeypatch, tmp_path):
        csv_path = tmp_path / "birthdays.csv"
        csv_path.write_text("Name,Birthday,PhoneNumber\n" "Alice,1990-01-01,+10000000000\n")

        monkeypatch.setenv("SMS_GATEWAY_USERNAME", "user")
        monkeypatch.setenv("SMS_GATEWAY_PASSWORD", "pass")
        monkeypatch.setenv("BIRTHDAY_CSV_PATH", str(csv_path))
        monkeypatch.setenv("STATE_FILE_PATH", str(tmp_path / "state.json"))
        monkeypatch.setenv("DRY_RUN", "false")

        exit_code = main_module.main()

        assert exit_code == 0


class TestMainRunSummaryMetadata:
    def test_step_summary_includes_trigger_and_timestamps(self, monkeypatch, tmp_path):
        csv_path = tmp_path / "birthdays.csv"
        csv_path.write_text("Name,Birthday,PhoneNumber\n" "Alice,1990-01-01,+10000000000\n")
        summary_path = tmp_path / "summary.md"

        monkeypatch.setenv("SMS_GATEWAY_USERNAME", "user")
        monkeypatch.setenv("SMS_GATEWAY_PASSWORD", "pass")
        monkeypatch.setenv("BIRTHDAY_CSV_PATH", str(csv_path))
        monkeypatch.setenv("STATE_FILE_PATH", str(tmp_path / "state.json"))
        monkeypatch.setenv("DRY_RUN", "false")
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
        monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
        monkeypatch.setenv("GITHUB_EVENT_SCHEDULE", "47 18 * * *")
        monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
        monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
        monkeypatch.setenv("GITHUB_RUN_ID", "999")

        exit_code = main_module.main()

        assert exit_code == 0
        content = summary_path.read_text(encoding="utf-8")
        assert "schedule" in content
        assert "47 18 * * *" in content
        assert "https://github.com/org/repo/actions/runs/999" in content
        assert "Started" in content
        assert "Completed" in content
