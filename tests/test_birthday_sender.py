from datetime import date, datetime
from unittest.mock import MagicMock

from birthday_sms.birthday_sender import BirthdaySender
from birthday_sms.config import AppConfig, SmsGatewayConfig
from birthday_sms.exceptions import RetryExhaustedError
from birthday_sms.message_builder import MessageBuilder
from birthday_sms.models import Contact, SendStatus
from birthday_sms.sms_gateway_client import SendSmsResponse
from birthday_sms.state_store import SentStateStore


def make_config(csv_path, state_path, dry_run=False) -> AppConfig:
    return AppConfig(
        csv_path=str(csv_path),
        timezone="Asia/Kolkata",
        default_message_template="Happy Birthday {FIRST_NAME}!",
        log_level="INFO",
        dry_run=dry_run,
        state_file_path=str(state_path),
        gateway=SmsGatewayConfig(
            base_url="https://api.sms-gate.app/3rdparty/v1",
            username="u",
            password="p",
            timeout_seconds=5,
            max_retries=1,
            retry_backoff_base_seconds=0.01,
            retry_backoff_max_seconds=0.01,
        ),
    )


def make_contact(**overrides) -> Contact:
    defaults = dict(
        name="Rahul Sharma",
        phone_number="+919876543210",
        birthday=date(2000, 7, 25),
        enabled=True,
    )
    defaults.update(overrides)
    return Contact(**defaults)


class FakeRepository:
    def __init__(self, contacts):
        self._contacts = contacts

    def load(self):
        return self._contacts


class TestBirthdaySender:
    def test_sends_sms_for_contact_with_birthday_today(self, tmp_path):
        today = date(2026, 7, 25)
        contact = make_contact(birthday=date(2000, 7, 25))
        gateway = MagicMock()
        gateway.send_sms.return_value = SendSmsResponse(
            message_id="abc",
            state="Pending",
            raw={},
        )

        sender = BirthdaySender(
            config=make_config(tmp_path / "c.csv", tmp_path / "state.json"),
            repository=FakeRepository([contact]),
            gateway_client=gateway,
            message_builder=MessageBuilder(),
            state_store=SentStateStore(tmp_path / "state.json"),
        )

        results = sender.run(today)

        assert len(results) == 1
        assert results[0].status == SendStatus.SENT
        gateway.send_sms.assert_called_once()

    def test_skips_contact_whose_birthday_is_not_today(self, tmp_path):
        today = date(2026, 1, 1)
        contact = make_contact(birthday=date(2000, 7, 25))
        gateway = MagicMock()

        sender = BirthdaySender(
            config=make_config(tmp_path / "c.csv", tmp_path / "state.json"),
            repository=FakeRepository([contact]),
            gateway_client=gateway,
            message_builder=MessageBuilder(),
            state_store=SentStateStore(tmp_path / "state.json"),
        )

        results = sender.run(today)

        assert results[0].status == SendStatus.SKIPPED_NOT_TODAY
        gateway.send_sms.assert_not_called()

    def test_skips_disabled_contact(self, tmp_path):
        today = date(2026, 7, 25)
        contact = make_contact(
            birthday=date(2000, 7, 25),
            enabled=False,
        )
        gateway = MagicMock()

        sender = BirthdaySender(
            config=make_config(tmp_path / "c.csv", tmp_path / "state.json"),
            repository=FakeRepository([contact]),
            gateway_client=gateway,
            message_builder=MessageBuilder(),
            state_store=SentStateStore(tmp_path / "state.json"),
        )

        results = sender.run(today)

        assert results[0].status == SendStatus.SKIPPED_DISABLED
        gateway.send_sms.assert_not_called()

    def test_does_not_resend_same_year(self, tmp_path):
        today = date(2026, 7, 25)
        contact = make_contact(birthday=date(2000, 7, 25))
        state_path = tmp_path / "state.json"

        state_store = SentStateStore(state_path)
        state_store.mark_sent(contact.phone_number, today.year)
        state_store.save()

        gateway = MagicMock()

        sender = BirthdaySender(
            config=make_config(tmp_path / "c.csv", state_path),
            repository=FakeRepository([contact]),
            gateway_client=gateway,
            message_builder=MessageBuilder(),
            state_store=SentStateStore(state_path),
        )

        results = sender.run(today)

        assert results[0].status == SendStatus.SKIPPED_ALREADY_SENT
        gateway.send_sms.assert_not_called()

    def test_dry_run_does_not_call_gateway(self, tmp_path):
        today = date(2026, 7, 25)
        contact = make_contact(birthday=date(2000, 7, 25))
        gateway = MagicMock()

        sender = BirthdaySender(
            config=make_config(
                tmp_path / "c.csv",
                tmp_path / "state.json",
                dry_run=True,
            ),
            repository=FakeRepository([contact]),
            gateway_client=gateway,
            message_builder=MessageBuilder(),
            state_store=SentStateStore(tmp_path / "state.json"),
        )

        results = sender.run(today)

        assert results[0].status == SendStatus.DRY_RUN
        gateway.send_sms.assert_not_called()

    def test_gateway_failure_is_recorded_not_raised(self, tmp_path):
        today = date(2026, 7, 25)
        contact = make_contact(birthday=date(2000, 7, 25))
        gateway = MagicMock()
        gateway.send_sms.side_effect = RetryExhaustedError(attempts=3)

        sender = BirthdaySender(
            config=make_config(tmp_path / "c.csv", tmp_path / "state.json"),
            repository=FakeRepository([contact]),
            gateway_client=gateway,
            message_builder=MessageBuilder(),
            state_store=SentStateStore(tmp_path / "state.json"),
        )

        results = sender.run(today)

        assert results[0].status == SendStatus.FAILED
        assert results[0].error is not None


class TestSendResultTimestamps:
    def test_sent_result_has_sent_at_and_retry_attempts(self, tmp_path):
        today = date(2026, 7, 25)
        contact = make_contact(birthday=date(2000, 7, 25))
        gateway = MagicMock()
        gateway.send_sms.return_value = SendSmsResponse(
            message_id="abc", state="Pending", raw={}, attempts=2
        )

        sender = BirthdaySender(
            config=make_config(tmp_path / "c.csv", tmp_path / "state.json"),
            repository=FakeRepository([contact]),
            gateway_client=gateway,
            message_builder=MessageBuilder(),
            state_store=SentStateStore(tmp_path / "state.json"),
            now=lambda: datetime(2026, 7, 25, 0, 17, 0),
        )

        results = sender.run(today)

        assert results[0].sent_at == "2026-07-25 00:17:00"
        assert results[0].retry_attempts == 2

    def test_failed_result_has_sent_at(self, tmp_path):
        today = date(2026, 7, 25)
        contact = make_contact(birthday=date(2000, 7, 25))
        gateway = MagicMock()
        gateway.send_sms.side_effect = RetryExhaustedError(3, None)

        sender = BirthdaySender(
            config=make_config(tmp_path / "c.csv", tmp_path / "state.json"),
            repository=FakeRepository([contact]),
            gateway_client=gateway,
            message_builder=MessageBuilder(),
            state_store=SentStateStore(tmp_path / "state.json"),
            now=lambda: datetime(2026, 7, 25, 0, 17, 0),
        )

        results = sender.run(today)

        assert results[0].sent_at == "2026-07-25 00:17:00"

    def test_delivered_result_has_delivered_at(self, tmp_path):
        today = date(2026, 7, 25)
        contact = make_contact(birthday=date(2000, 7, 25))
        gateway = MagicMock()
        gateway.send_sms.return_value = SendSmsResponse(
            message_id="abc", state="Pending", raw={}, attempts=1
        )
        tracker = MagicMock()
        tracker.track.return_value = {"abc": "Delivered"}

        times = iter(
            [
                datetime(2026, 7, 25, 0, 17, 0),
                datetime(2026, 7, 25, 0, 18, 30),
            ]
        )

        sender = BirthdaySender(
            config=make_config(tmp_path / "c.csv", tmp_path / "state.json"),
            repository=FakeRepository([contact]),
            gateway_client=gateway,
            message_builder=MessageBuilder(),
            state_store=SentStateStore(tmp_path / "state.json"),
            delivery_tracker=tracker,
            now=lambda: next(times),
        )

        results = sender.run(today)

        assert results[0].sent_at == "2026-07-25 00:17:00"
        assert results[0].delivered_at == "2026-07-25 00:18:30"
