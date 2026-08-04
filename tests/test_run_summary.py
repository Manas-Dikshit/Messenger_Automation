"""Tests for the GitHub Actions step-summary writer."""

from datetime import date

from birthday_sms.models import Contact, SendResult, SendStatus
from birthday_sms.run_summary import build_summary_markdown, write_github_step_summary


def make_contact(name="Rahul Sharma", phone="+919876543210"):
    return Contact(
        name=name,
        phone_number=phone,
        birthday=date(2000, 7, 25),
        enabled=True,
    )


class TestBuildSummaryMarkdown:
    def test_contains_status_counts(self):
        results = [
            SendResult(contact=make_contact(), status=SendStatus.SENT, message_id="m1"),
            SendResult(contact=make_contact("B", "+911"), status=SendStatus.SKIPPED_NOT_TODAY),
        ]

        md = build_summary_markdown(results, delivery_states={}, unconfirmed={})

        assert "SENT" in md
        assert "SKIPPED_NOT_TODAY" in md

    def test_sent_rows_show_delivery_state(self):
        results = [
            SendResult(contact=make_contact(), status=SendStatus.SENT, message_id="m1"),
        ]

        md = build_summary_markdown(results, delivery_states={"m1": "Delivered"}, unconfirmed={})

        assert "Rahul Sharma" in md
        assert "Delivered" in md

    def test_unconfirmed_section_listed(self):
        md = build_summary_markdown(
            [], delivery_states={}, unconfirmed={"m9": {"phone": "+911", "year": 2026}}
        )

        assert "m9" in md
        assert "+911" in md

    def test_no_birthdays_message(self):
        results = [
            SendResult(contact=make_contact(), status=SendStatus.SKIPPED_NOT_TODAY),
        ]

        md = build_summary_markdown(results, delivery_states={}, unconfirmed={})

        assert "No birthdays today" in md


class TestWriteGithubStepSummary:
    def test_appends_to_summary_file(self, tmp_path, monkeypatch):
        summary_file = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        write_github_step_summary("# Hello")

        assert "# Hello" in summary_file.read_text(encoding="utf-8")

    def test_noop_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

        write_github_step_summary("# Hello")  # must not raise
