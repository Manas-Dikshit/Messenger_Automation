"""Orchestrates a single run: load contacts, find today's birthdays,
render messages, send via the gateway, and record results."""

from __future__ import annotations

import logging
from datetime import date

from birthday_sms.config import AppConfig
from birthday_sms.csv_reader import CsvContactRepository
from birthday_sms.exceptions import RetryExhaustedError, SmsGatewayError
from birthday_sms.message_builder import MessageBuilder
from birthday_sms.models import Contact, SendResult, SendStatus
from birthday_sms.sms_gateway_client import SmsGatewayClient
from birthday_sms.state_store import SentStateStore

logger = logging.getLogger(__name__)


class BirthdaySender:
    """Coordinates the end-to-end birthday SMS workflow."""

    def __init__(
        self,
        config: AppConfig,
        repository: CsvContactRepository,
        gateway_client: SmsGatewayClient,
        message_builder: MessageBuilder,
        state_store: SentStateStore,
    ) -> None:
        self._config = config
        self._repository = repository
        self._gateway_client = gateway_client
        self._message_builder = message_builder
        self._state_store = state_store

    def run(self, today: date) -> list[SendResult]:
        """Execute one full run for the given date and return results."""
        logger.info("Loading contacts from %s", self._config.csv_path)
        contacts = self._repository.load()
        logger.info("Loaded %d contact(s).", len(contacts))

        results: list[SendResult] = []
        for contact in contacts:
            result = self._process_contact(contact, today)
            results.append(result)

        self._state_store.save()
        self._log_summary(results)
        return results

    def _process_contact(self, contact: Contact, today: date) -> SendResult:
        if not contact.enabled:
            logger.debug("Skipping %s: disabled in CSV.", contact.name)
            return SendResult(contact=contact, status=SendStatus.SKIPPED_DISABLED)

        if not contact.is_birthday_today(today):
            return SendResult(contact=contact, status=SendStatus.SKIPPED_NOT_TODAY)

        logger.info("Birthday found: %s (%s)", contact.name, contact.phone_number)

        if self._state_store.already_sent(contact.phone_number, today.year):
            logger.info("Already sent to %s this year - skipping.", contact.name)
            return SendResult(contact=contact, status=SendStatus.SKIPPED_ALREADY_SENT)

        template = contact.message_template or self._config.default_message_template
        rendered_message = self._message_builder.render(template, contact, today)

        if self._config.dry_run:
            logger.info("[DRY RUN] Would send to %s: %s", contact.phone_number, rendered_message)
            return SendResult(
                contact=contact,
                status=SendStatus.DRY_RUN,
                rendered_message=rendered_message,
            )

        try:
            response = self._gateway_client.send_sms(contact.phone_number, rendered_message)
        except (SmsGatewayError, RetryExhaustedError) as exc:
            logger.error("Failed to send SMS to %s: %s", contact.name, exc)
            return SendResult(
                contact=contact,
                status=SendStatus.FAILED,
                error=str(exc),
                rendered_message=rendered_message,
            )

        self._state_store.mark_sent(contact.phone_number, today.year)
        logger.info(
            "SMS Sent to %s (%s) - gateway message id=%s state=%s",
            contact.name,
            contact.phone_number,
            response.message_id,
            response.state,
        )
        return SendResult(
            contact=contact,
            status=SendStatus.SENT,
            message_id=response.message_id,
            rendered_message=rendered_message,
        )

    @staticmethod
    def _log_summary(results: list[SendResult]) -> None:
        counts: dict[SendStatus, int] = {}
        for result in results:
            counts[result.status] = counts.get(result.status, 0) + 1

        logger.info(
            "Run summary: %s",
            ", ".join(f"{status.value}={count}" for status, count in counts.items())
            or "no contacts",
        )
