"""HTTP client for SMS Gateway for Android (capcom6) - Cloud Mode.

Cloud Mode means the Android app maintains an outbound connection to
`api.sms-gate.app` (or a self-hosted relay), so this script never
needs to know the phone's IP address or be on the same network. We
simply POST to the cloud API with HTTP Basic Auth, and the cloud
service forwards the request to the teacher's phone, which sends the
real SMS via its own SIM.

Reference: https://sms-gate.app/integration/cloud/
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

import requests
from requests.auth import HTTPBasicAuth

from birthday_sms.config import SmsGatewayConfig
from birthday_sms.constants import (
    RETRYABLE_STATUS_CODES,
    SMS_GATEWAY_MESSAGES_ENDPOINT,
)
from birthday_sms.exceptions import (
    RetryExhaustedError,
    SmsGatewayAuthenticationError,
    SmsGatewayResponseError,
    SmsGatewayTimeoutError,
    SmsGatewayUnavailableError,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SendSmsResponse:
    """Parsed response from a successful send request."""

    message_id: str
    state: str
    raw: dict


class SmsGatewayClient:
    """Thin, retrying wrapper around the SMS Gateway REST API."""

    def __init__(
        self,
        config: SmsGatewayConfig,
        session: requests.Session | None = None,
    ) -> None:
        self._config = config
        self._session = session or requests.Session()

    def send_sms(self, phone_number: str, message: str) -> SendSmsResponse:
        """Send a single SMS via the gateway, retrying transient failures.

        Args:
            phone_number: E.164 formatted recipient number.
            message: Rendered message body.

        Returns:
            SendSmsResponse with the gateway-assigned message id.

        Raises:
            SmsGatewayAuthenticationError:
                Raised on HTTP 401/403 (not retried).
            RetryExhaustedError:
                Raised if all retry attempts fail.
        """
        url = f"{self._config.base_url}{SMS_GATEWAY_MESSAGES_ENDPOINT}"

        payload: dict = {
            "message": message,
            "phoneNumbers": [phone_number],
        }

        if self._config.default_sender_sim:
            payload["simNumber"] = self._config.default_sender_sim

        last_error: Exception | None = None

        for attempt in range(1, self._config.max_retries + 1):
            try:
                response = self._session.post(
                    url,
                    json=payload,
                    auth=HTTPBasicAuth(
                        self._config.username,
                        self._config.password,
                    ),
                    timeout=self._config.timeout_seconds,
                )

            except requests.Timeout:
                last_error = SmsGatewayTimeoutError(
                    f"Request timed out after {self._config.timeout_seconds}s."
                )
                logger.warning(
                    "Attempt %d/%d timed out.",
                    attempt,
                    self._config.max_retries,
                )

            except requests.ConnectionError as exc:
                last_error = SmsGatewayUnavailableError(
                    "Could not reach SMS Gateway. Is the phone online and "
                    "connected to Cloud Mode?"
                )
                logger.warning(
                    "Attempt %d/%d - connection error: %s",
                    attempt,
                    self._config.max_retries,
                    exc,
                )

            else:
                if response.status_code in (401, 403):
                    raise SmsGatewayAuthenticationError(
                        "Authentication failed (HTTP "
                        f"{response.status_code}). Check "
                        "SMS_GATEWAY_USERNAME / SMS_GATEWAY_PASSWORD secrets."
                    )

                if response.status_code // 100 == 2:
                    return self._parse_success(response)

                if response.status_code in RETRYABLE_STATUS_CODES:
                    last_error = SmsGatewayUnavailableError(
                        f"Gateway returned transient error HTTP {response.status_code}."
                    )
                    logger.warning(
                        "Attempt %d/%d - transient HTTP %d: %s",
                        attempt,
                        self._config.max_retries,
                        response.status_code,
                        response.text[:300],
                    )
                else:
                    raise SmsGatewayResponseError(
                        f"Gateway rejected the request: HTTP "
                        f"{response.status_code} - {response.text[:300]}"
                    )

            if attempt < self._config.max_retries:
                self._sleep_with_backoff(attempt)

        raise RetryExhaustedError(self._config.max_retries, last_error)

    def get_message_state(self, message_id: str) -> SendSmsResponse:
        """Fetch the current state of a previously sent message.

        Single attempt, no retry loop - callers poll, so polling is the
        retry mechanism.

        Raises:
            SmsGatewayAuthenticationError: on HTTP 401/403.
            SmsGatewayResponseError: on any other non-2xx response.
            SmsGatewayTimeoutError / SmsGatewayUnavailableError:
                on network-level failures.
        """
        url = f"{self._config.base_url}{SMS_GATEWAY_MESSAGES_ENDPOINT}/{message_id}"

        try:
            response = self._session.get(
                url,
                auth=HTTPBasicAuth(self._config.username, self._config.password),
                timeout=self._config.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise SmsGatewayTimeoutError(
                f"State request timed out after {self._config.timeout_seconds}s."
            ) from exc
        except requests.ConnectionError as exc:
            raise SmsGatewayUnavailableError(
                "Could not reach SMS Gateway for state check."
            ) from exc

        if response.status_code in (401, 403):
            raise SmsGatewayAuthenticationError(
                f"Authentication failed (HTTP {response.status_code}) fetching message state."
            )

        if response.status_code // 100 != 2:
            raise SmsGatewayResponseError(
                f"Gateway state request failed: HTTP "
                f"{response.status_code} - {response.text[:300]}"
            )

        return self._parse_success(response)

    def _sleep_with_backoff(self, attempt: int) -> None:
        base = self._config.retry_backoff_base_seconds
        max_delay = self._config.retry_backoff_max_seconds

        delay = min(base * (2 ** (attempt - 1)), max_delay)
        jitter = random.uniform(0, delay * 0.25)
        total_delay = delay + jitter

        logger.info(
            "Retrying in %.1fs (attempt %d)...",
            total_delay,
            attempt + 1,
        )

        time.sleep(total_delay)

    @staticmethod
    def _parse_success(response: requests.Response) -> SendSmsResponse:
        try:
            data = response.json()
        except ValueError as exc:
            raise SmsGatewayResponseError(
                f"Gateway returned a non-JSON success response: " f"{response.text[:300]}"
            ) from exc

        message_id = data.get("id")
        state = data.get("state", "Unknown")

        if not message_id:
            raise SmsGatewayResponseError(f"Gateway response missing 'id' field: {data}")

        return SendSmsResponse(
            message_id=message_id,
            state=state,
            raw=data,
        )
