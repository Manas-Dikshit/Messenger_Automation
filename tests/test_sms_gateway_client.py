import responses

from birthday_sms.config import SmsGatewayConfig
from birthday_sms.exceptions import (
    RetryExhaustedError,
    SmsGatewayAuthenticationError,
    SmsGatewayResponseError,
)
from birthday_sms.sms_gateway_client import SmsGatewayClient

import pytest


def make_config(**overrides) -> SmsGatewayConfig:
    defaults = dict(
        base_url="https://api.sms-gate.app/3rdparty/v1",
        username="user",
        password="pass",
        timeout_seconds=5,
        max_retries=3,
        retry_backoff_base_seconds=0.01,  # keep tests fast
        retry_backoff_max_seconds=0.05,
        default_sender_sim=None,
    )
    defaults.update(overrides)
    return SmsGatewayConfig(**defaults)


class TestSmsGatewayClient:
    @responses.activate
    def test_send_sms_success(self):
        responses.add(
            responses.POST,
            "https://api.sms-gate.app/3rdparty/v1/messages",
            json={"id": "msg-123", "state": "Pending"},
            status=201,
        )
        client = SmsGatewayClient(make_config())

        result = client.send_sms("+919876543210", "Happy Birthday!")

        assert result.message_id == "msg-123"
        assert result.state == "Pending"

    @responses.activate
    def test_send_sms_authentication_failure_not_retried(self):
        responses.add(
            responses.POST,
            "https://api.sms-gate.app/3rdparty/v1/messages",
            json={"error": "unauthorized"},
            status=401,
        )
        client = SmsGatewayClient(make_config())

        with pytest.raises(SmsGatewayAuthenticationError):
            client.send_sms("+919876543210", "Happy Birthday!")

        assert len(responses.calls) == 1  # no retry on auth failure

    @responses.activate
    def test_send_sms_retries_on_transient_error_then_succeeds(self):
        responses.add(
            responses.POST,
            "https://api.sms-gate.app/3rdparty/v1/messages",
            json={"error": "server error"},
            status=503,
        )
        responses.add(
            responses.POST,
            "https://api.sms-gate.app/3rdparty/v1/messages",
            json={"id": "msg-456", "state": "Pending"},
            status=200,
        )
        client = SmsGatewayClient(make_config())

        result = client.send_sms("+919876543210", "Happy Birthday!")

        assert result.message_id == "msg-456"
        assert len(responses.calls) == 2

    @responses.activate
    def test_send_sms_gives_up_after_max_retries(self):
        for _ in range(3):
            responses.add(
                responses.POST,
                "https://api.sms-gate.app/3rdparty/v1/messages",
                json={"error": "server error"},
                status=503,
            )
        client = SmsGatewayClient(make_config(max_retries=3))

        with pytest.raises(RetryExhaustedError):
            client.send_sms("+919876543210", "Happy Birthday!")

        assert len(responses.calls) == 3

    @responses.activate
    def test_send_sms_non_retryable_client_error_raises_immediately(self):
        responses.add(
            responses.POST,
            "https://api.sms-gate.app/3rdparty/v1/messages",
            json={"error": "bad request"},
            status=400,
        )
        client = SmsGatewayClient(make_config())

        with pytest.raises(SmsGatewayResponseError):
            client.send_sms("+919876543210", "Happy Birthday!")

        assert len(responses.calls) == 1
