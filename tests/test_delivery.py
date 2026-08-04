"""Tests for delivery confirmation: message-state polling and tracking."""

import json
from datetime import date
from unittest.mock import MagicMock

import pytest
import responses

from birthday_sms.birthday_sender import BirthdaySender
from birthday_sms.config import AppConfig, SmsGatewayConfig
from birthday_sms.delivery_tracker import DeliveryTracker
from birthday_sms.exceptions import SmsGatewayResponseError
from birthday_sms.message_builder import MessageBuilder
from birthday_sms.sms_gateway_client import SendSmsResponse, SmsGatewayClient
from birthday_sms.state_store import SentStateStore

BASE_URL = "https://api.sms-gate.app/3rdparty/v1"


def make_config(**overrides) -> SmsGatewayConfig:
    defaults = dict(
        base_url=BASE_URL,
        username="user",
        password="pass",
        timeout_seconds=5,
        max_retries=3,
        retry_backoff_base_seconds=0.01,
        retry_backoff_max_seconds=0.05,
        default_sender_sim=None,
    )
    defaults.update(overrides)
    return SmsGatewayConfig(**defaults)


class TestGetMessageState:
    @responses.activate
    def test_get_message_state_success(self):
        responses.add(
            responses.GET,
            f"{BASE_URL}/messages/msg-123",
            json={"id": "msg-123", "state": "Delivered"},
            status=200,
        )
        client = SmsGatewayClient(make_config())

        result = client.get_message_state("msg-123")

        assert result.message_id == "msg-123"
        assert result.state == "Delivered"

    @responses.activate
    def test_get_message_state_error_status_raises(self):
        responses.add(
            responses.GET,
            f"{BASE_URL}/messages/msg-404",
            json={"error": "not found"},
            status=404,
        )
        client = SmsGatewayClient(make_config())

        with pytest.raises(SmsGatewayResponseError):
            client.get_message_state("msg-404")


class FakeStateClient:
    """Returns a scripted sequence of states per message id."""

    def __init__(self, sequences: dict[str, list[str]]) -> None:
        self._sequences = sequences
        self.calls: list[str] = []

    def get_message_state(self, message_id: str):
        self.calls.append(message_id)
        seq = self._sequences[message_id]
        state = seq.pop(0) if len(seq) > 1 else seq[0]

        class _Resp:
            pass

        resp = _Resp()
        resp.message_id = message_id
        resp.state = state
        return resp


def make_tracker(client, window=100.0):
    fake_time = {"now": 0.0}

    def monotonic():
        return fake_time["now"]

    def sleep(seconds):
        fake_time["now"] += seconds

    return DeliveryTracker(
        client,
        poll_interval_seconds=10.0,
        poll_window_seconds=window,
        sleep=sleep,
        monotonic=monotonic,
    )


class TestDeliveryTracker:
    def test_stops_early_when_all_terminal(self):
        client = FakeStateClient({"a": ["Delivered"], "b": ["Failed"]})
        tracker = make_tracker(client)

        states = tracker.track(["a", "b"])

        assert states == {"a": "Delivered", "b": "Failed"}
        assert client.calls == ["a", "b"]  # one poll round only

    def test_polls_until_delivered(self):
        client = FakeStateClient({"a": ["Pending", "Sent", "Delivered"]})
        tracker = make_tracker(client)

        states = tracker.track(["a"])

        assert states == {"a": "Delivered"}
        assert client.calls == ["a", "a", "a"]

    def test_window_expiry_returns_last_known_state(self):
        client = FakeStateClient({"a": ["Pending"]})
        tracker = make_tracker(client, window=25.0)

        states = tracker.track(["a"])

        assert states == {"a": "Pending"}
        # polled at t=0, 10, 20 -> window 25 exhausted
        assert client.calls == ["a", "a", "a"]

    def test_empty_input_no_polling(self):
        client = FakeStateClient({})
        tracker = make_tracker(client)

        assert tracker.track([]) == {}
        assert client.calls == []


class TestStateStoreUnconfirmed:
    def test_mark_and_list_unconfirmed(self, tmp_path):
        store = SentStateStore(tmp_path / "state.json")

        store.mark_unconfirmed("msg-1", "+911111111111", 2026)

        assert store.unconfirmed() == {"msg-1": {"phone": "+911111111111", "year": 2026}}

    def test_resolve_unconfirmed_removes_entry(self, tmp_path):
        store = SentStateStore(tmp_path / "state.json")
        store.mark_unconfirmed("msg-1", "+911111111111", 2026)

        store.resolve_unconfirmed("msg-1")

        assert store.unconfirmed() == {}

    def test_unconfirmed_persists_across_save_and_reload(self, tmp_path):
        path = tmp_path / "state.json"
        store = SentStateStore(path)
        store.mark_sent("+911111111111", 2026)
        store.mark_unconfirmed("msg-1", "+911111111111", 2026)
        store.save()

        reloaded = SentStateStore(path)

        assert reloaded.already_sent("+911111111111", 2026)
        assert "msg-1" in reloaded.unconfirmed()

    def test_legacy_flat_file_migrates(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"+911111111111:2025": True}), encoding="utf-8")

        store = SentStateStore(path)

        assert store.already_sent("+911111111111", 2025)
        assert store.unconfirmed() == {}


def make_app_config(state_path) -> AppConfig:
    return AppConfig(
        csv_path="unused.csv",
        timezone="Asia/Kolkata",
        default_message_template="Happy Birthday {FIRST_NAME}!",
        log_level="INFO",
        dry_run=False,
        state_file_path=str(state_path),
        gateway=make_config(),
    )


class FakeRepository:
    def __init__(self, contacts):
        self._contacts = contacts

    def load(self):
        return self._contacts


def make_contact():
    from birthday_sms.models import Contact

    return Contact(
        name="Rahul Sharma",
        phone_number="+919876543210",
        birthday=date(2000, 7, 25),
        enabled=True,
    )


def make_sender(tmp_path, gateway, tracker, contacts):
    store = SentStateStore(tmp_path / "state.json")
    sender = BirthdaySender(
        config=make_app_config(tmp_path / "state.json"),
        repository=FakeRepository(contacts),
        gateway_client=gateway,
        message_builder=MessageBuilder(),
        state_store=store,
        delivery_tracker=tracker,
    )
    return sender, store


class TestSenderDeliveryIntegration:
    def test_unconfirmed_state_recorded_when_not_delivered(self, tmp_path):
        gateway = MagicMock()
        gateway.send_sms.return_value = SendSmsResponse("msg-1", "Pending", {})
        tracker = MagicMock()
        tracker.track.return_value = {"msg-1": "Pending"}
        sender, store = make_sender(tmp_path, gateway, tracker, [make_contact()])

        sender.run(date(2026, 7, 25))

        tracker.track.assert_called_once_with(["msg-1"])
        assert "msg-1" in store.unconfirmed()

    def test_delivered_message_not_recorded_unconfirmed(self, tmp_path):
        gateway = MagicMock()
        gateway.send_sms.return_value = SendSmsResponse("msg-1", "Pending", {})
        tracker = MagicMock()
        tracker.track.return_value = {"msg-1": "Delivered"}
        sender, store = make_sender(tmp_path, gateway, tracker, [make_contact()])

        sender.run(date(2026, 7, 25))

        assert store.unconfirmed() == {}

    def test_previous_unconfirmed_rechecked_and_resolved(self, tmp_path):
        gateway = MagicMock()
        gateway.get_message_state.return_value = SendSmsResponse("old-1", "Delivered", {})
        tracker = MagicMock()
        tracker.track.return_value = {}
        sender, store = make_sender(tmp_path, gateway, tracker, [])
        store.mark_unconfirmed("old-1", "+911111111111", 2026)

        sender.run(date(2026, 1, 1))

        gateway.get_message_state.assert_called_once_with("old-1")
        assert store.unconfirmed() == {}

    def test_previous_unconfirmed_kept_when_still_pending(self, tmp_path):
        gateway = MagicMock()
        gateway.get_message_state.return_value = SendSmsResponse("old-1", "Pending", {})
        tracker = MagicMock()
        tracker.track.return_value = {}
        sender, store = make_sender(tmp_path, gateway, tracker, [])
        store.mark_unconfirmed("old-1", "+911111111111", 2026)

        sender.run(date(2026, 1, 1))

        assert "old-1" in store.unconfirmed()

    def test_no_tracker_means_no_polling(self, tmp_path):
        gateway = MagicMock()
        gateway.send_sms.return_value = SendSmsResponse("msg-1", "Pending", {})
        sender, store = make_sender(tmp_path, gateway, None, [make_contact()])

        results = sender.run(date(2026, 7, 25))

        assert results[0].status.value == "SENT"
        assert store.unconfirmed() == {}


class TestDeliveryConfig:
    def test_defaults(self, monkeypatch):
        monkeypatch.setenv("SMS_GATEWAY_USERNAME", "u")
        monkeypatch.setenv("SMS_GATEWAY_PASSWORD", "p")

        config = AppConfig.from_env()

        assert config.delivery_poll_enabled is True
        assert config.delivery_poll_interval_seconds == 30.0
        assert config.delivery_poll_window_seconds == 600.0

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("SMS_GATEWAY_USERNAME", "u")
        monkeypatch.setenv("SMS_GATEWAY_PASSWORD", "p")
        monkeypatch.setenv("DELIVERY_POLL_ENABLED", "false")
        monkeypatch.setenv("DELIVERY_POLL_INTERVAL_SECONDS", "5")
        monkeypatch.setenv("DELIVERY_POLL_WINDOW_SECONDS", "60")

        config = AppConfig.from_env()

        assert config.delivery_poll_enabled is False
        assert config.delivery_poll_interval_seconds == 5.0
        assert config.delivery_poll_window_seconds == 60.0

    def test_delivery_states_exposed_after_run(self, tmp_path):
        gateway = MagicMock()
        gateway.send_sms.return_value = SendSmsResponse("msg-1", "Pending", {})
        tracker = MagicMock()
        tracker.track.return_value = {"msg-1": "Delivered"}
        sender, _ = make_sender(tmp_path, gateway, tracker, [make_contact()])

        sender.run(date(2026, 7, 25))

        assert sender.delivery_states == {"msg-1": "Delivered"}
