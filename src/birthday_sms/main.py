"""CLI entrypoint. Invoked by GitHub Actions as:

    python -m birthday_sms.main

Exit codes:
    0 - run completed (individual send failures are logged, not fatal)
    1 - configuration or CSV-level error that prevented the run entirely
"""

from __future__ import annotations

import logging
import sys

from birthday_sms.birthday_sender import BirthdaySender
from birthday_sms.config import AppConfig
from birthday_sms.csv_reader import CsvContactRepository
from birthday_sms.date_utils import today_in_timezone
from birthday_sms.exceptions import ConfigurationError, CsvError
from birthday_sms.logger import configure_logging
from birthday_sms.message_builder import MessageBuilder
from birthday_sms.models import SendStatus
from birthday_sms.sms_gateway_client import SmsGatewayClient
from birthday_sms.state_store import SentStateStore

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        config = AppConfig.from_env()
    except ConfigurationError as exc:
        # Logging isn't configured yet if this fails, so print directly.
        print(f"CONFIGURATION ERROR: {exc}", file=sys.stderr)
        return 1

    configure_logging(level=config.log_level)

    logger.info(
        "Birthday SMS Automation starting. dry_run=%s",
        config.dry_run,
    )

    try:
        # GitHub Actions now runs shortly AFTER midnight.
        # Therefore, we simply resolve today's date in the configured
        # timezone instead of calculating the next midnight.
        target_date = today_in_timezone(config.timezone)
    except ValueError as exc:
        logger.error("Timezone error: %s", exc)
        return 1

    logger.info(
        "Checking birthdays for %s in timezone %s",
        target_date.isoformat(),
        config.timezone,
    )

    repository = CsvContactRepository(config.csv_path)
    gateway_client = SmsGatewayClient(config.gateway)
    message_builder = MessageBuilder()
    state_store = SentStateStore(config.state_file_path)

    sender = BirthdaySender(
        config=config,
        repository=repository,
        gateway_client=gateway_client,
        message_builder=message_builder,
        state_store=state_store,
    )

    try:
        results = sender.run(target_date)
    except CsvError as exc:
        logger.error("CSV error - aborting run: %s", exc)
        return 1

    failures = [r for r in results if r.status == SendStatus.FAILED]

    if failures:
        logger.warning(
            "%d message(s) failed to send this run.",
            len(failures),
        )

        # Individual SMS failures are logged but do not fail the
        # entire GitHub Actions workflow.
        #
        # This preserves the existing behaviour.

    logger.info("Birthday SMS Automation finished.")

    return 0


if __name__ == "__main__":
    sys.exit(main())