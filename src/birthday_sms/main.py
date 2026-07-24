"""CLI entrypoint. Invoked by GitHub Actions as:

    python -m birthday_sms.main

Exit codes:
    0 - run completed (individual send failures are logged, not fatal)
    1 - configuration or CSV-level error that prevented the run entirely
"""

from __future__ import annotations

import logging
import sys
import time

from birthday_sms.birthday_sender import BirthdaySender
from birthday_sms.config import AppConfig
from birthday_sms.csv_reader import CsvContactRepository
from birthday_sms.date_utils import next_midnight_date, seconds_until_next_midnight
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
    logger.info("Birthday SMS Automation starting. dry_run=%s", config.dry_run)

    try:
        # This workflow runs at 23:50 IST (see .github/workflows/daily.yml),
        # 10 minutes before the midnight it should actually send on. So the
        # date to check birthdays against is the day about to begin, not
        # today's date at the moment the runner starts.
        target_date = next_midnight_date(config.timezone)
    except ValueError as exc:
        logger.error("Timezone error: %s", exc)
        return 1

    logger.info(
        "Resolved target date as %s (next midnight in %s)",
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
        if not config.dry_run:
            # Skip the midnight wait entirely on nights with no birthdays,
            # so the workflow finishes in seconds instead of ~10 minutes.
            if not sender.has_matching_birthday(target_date):
                logger.info(
                    "No birthdays found for %s - nothing to do, exiting.",
                    target_date.isoformat(),
                )
                return 0

            wait_seconds = seconds_until_next_midnight(config.timezone)
            if wait_seconds > 0:
                logger.info(
                    "Birthday(s) found for %s. Waiting %.0f second(s) until "
                    "00:00 %s before sending.",
                    target_date.isoformat(),
                    wait_seconds,
                    config.timezone,
                )
                time.sleep(wait_seconds)

        results = sender.run(target_date)
    except CsvError as exc:
        logger.error("CSV error - aborting run: %s", exc)
        return 1

    failures = [r for r in results if r.status == SendStatus.FAILED]
    if failures:
        logger.warning("%d message(s) failed to send this run.", len(failures))
        # Non-zero-but-not-fatal: we still exit 0 so GitHub Actions doesn't
        # mark the whole workflow red over one flaky recipient, but the
        # failure is clearly visible in the logs above.

    logger.info("Birthday SMS Automation finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())