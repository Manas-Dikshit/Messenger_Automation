"""GitHub Actions step summary for a run.

Renders a small Markdown report (status counts, per-send delivery
outcome, unconfirmed backlog) and appends it to the file GitHub
exposes via the ``GITHUB_STEP_SUMMARY`` env var. Outside of GitHub
Actions the env var is absent and writing is a no-op, so local runs
are unaffected.
"""

from __future__ import annotations

import logging
import os

from birthday_sms.models import SendResult, SendStatus

logger = logging.getLogger(__name__)


def build_summary_markdown(
    results: list[SendResult],
    delivery_states: dict[str, str],
    unconfirmed: dict[str, dict],
) -> str:
    """Render the run report as GitHub-flavored Markdown."""
    lines: list[str] = ["# Birthday SMS Run Summary", ""]

    counts: dict[SendStatus, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    lines += ["## Status counts", ""]
    if counts:
        lines += ["| Status | Count |", "| --- | --- |"]
        lines += [f"| {status.value} | {count} |" for status, count in sorted(counts.items())]
    else:
        lines.append("_No contacts processed._")
    lines.append("")

    attempted = [
        r for r in results if r.status in (SendStatus.SENT, SendStatus.FAILED, SendStatus.DRY_RUN)
    ]
    lines += ["## Today's birthdays", ""]
    if attempted:
        lines += [
            "| Contact | Phone | Send status | Delivery |",
            "| --- | --- | --- | --- |",
        ]
        for result in attempted:
            delivery = delivery_states.get(result.message_id or "", "-")
            lines.append(
                f"| {result.contact.name} | {result.contact.phone_number} "
                f"| {result.status.value} | {delivery} |"
            )
    else:
        lines.append("No birthdays today.")
    lines.append("")

    lines += ["## Unconfirmed deliveries (will re-check next run)", ""]
    if unconfirmed:
        lines += ["| Message ID | Phone | Year |", "| --- | --- | --- |"]
        lines += [
            f"| {message_id} | {info.get('phone', '?')} | {info.get('year', '?')} |"
            for message_id, info in sorted(unconfirmed.items())
        ]
    else:
        lines.append("None - all deliveries confirmed.")
    lines.append("")

    return "\n".join(lines)


def write_github_step_summary(markdown: str) -> None:
    """Append markdown to the GitHub step summary file, if available."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        logger.debug("GITHUB_STEP_SUMMARY not set; skipping step summary.")
        return
    try:
        with open(path, "a", encoding="utf-8") as summary_file:
            summary_file.write(markdown + "\n")
    except OSError as exc:
        logger.warning("Could not write step summary: %s", exc)
