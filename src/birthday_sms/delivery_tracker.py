"""Polls the gateway for delivery states of sent messages.

Runs after all sends complete. Polls `GET /messages/{id}` for each
message until it reaches a terminal state (Delivered/Failed) or the
polling window expires. Messages still non-terminal at the end of the
window (typically because the recipient's phone is off) are reported
with their last known state so the caller can record them as
unconfirmed and re-check on the next run.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Protocol

from birthday_sms.constants import DELIVERY_TERMINAL_STATES
from birthday_sms.exceptions import SmsGatewayError

logger = logging.getLogger(__name__)


class _StateClient(Protocol):
    def get_message_state(self, message_id: str): ...


class DeliveryTracker:
    """Bounded polling loop over gateway message states."""

    def __init__(
        self,
        client: _StateClient,
        poll_interval_seconds: float,
        poll_window_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._poll_interval = poll_interval_seconds
        self._poll_window = poll_window_seconds
        self._sleep = sleep
        self._monotonic = monotonic

    def track(self, message_ids: list[str]) -> dict[str, str]:
        """Poll until all messages are terminal or the window expires.

        Returns a mapping of message id -> last known state.
        """
        states: dict[str, str] = {mid: "Unknown" for mid in message_ids}
        if not message_ids:
            return states

        deadline = self._monotonic() + self._poll_window

        while True:
            pending = [
                mid for mid, state in states.items() if state not in DELIVERY_TERMINAL_STATES
            ]
            for message_id in pending:
                try:
                    response = self._client.get_message_state(message_id)
                except SmsGatewayError as exc:
                    logger.warning("Could not fetch state for %s: %s", message_id, exc)
                    continue
                states[message_id] = response.state

            if all(state in DELIVERY_TERMINAL_STATES for state in states.values()):
                break

            if self._monotonic() + self._poll_interval > deadline:
                logger.info(
                    "Delivery polling window expired with %d message(s) unconfirmed.",
                    sum(1 for s in states.values() if s not in DELIVERY_TERMINAL_STATES),
                )
                break

            self._sleep(self._poll_interval)

        return states
