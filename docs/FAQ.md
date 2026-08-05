# Frequently Asked Questions

**Q: Does my PC need to be on for this to work?**
No. The scheduled job runs entirely on GitHub's infrastructure. The
only device that needs to be on and connected to the internet is the
teacher's Android phone.

**Q: Why does the project mention cron-job.org? Isn't GitHub Actions'
own schedule enough?**
GitHub's own `schedule:` trigger has no timing guarantee - GitHub's
own docs say it can be delayed during high load, or occasionally
dropped, with no maximum delay published. In practice this project
observed delays of over an hour and at least one dropped run.
[cron-job.org](https://cron-job.org) (free) calls the same workflow
via the `workflow_dispatch` API on a precise schedule instead, which
doesn't share GitHub's scheduling queue and runs promptly. It's
optional - GitHub's own cron is kept as a free backup - but
recommended if on-time delivery matters to you. See
[`DEPLOYMENT.md`](DEPLOYMENT.md#step-9b---recommended-external-scheduler-for-on-time-triggers).

**Q: Does this cost money?**
GitHub Actions is free for a daily job at this scale on most account
tiers. The SMS Gateway app itself is open source. The only cost is
whatever the teacher's mobile carrier charges for sending a normal SMS
from their plan - same as texting anyone manually.

**Q: Does this use Twilio, MSG91, TextLocal, or any bulk SMS API?**
No. By design, this project uses none of those. SMS is sent from the
teacher's own SIM card via the SMS Gateway for Android app.

**Q: Can it send WhatsApp or Telegram messages instead?**
No - this project is scoped to SMS only, sent via the phone's SIM,
per the stated requirement.

**Q: What happens if the teacher's phone is off when the job runs?**
The send attempt fails after retrying, is logged clearly as `FAILED`,
and is **not** marked as sent - so re-running the workflow manually
once the phone is back online will successfully deliver it.

**Q: What if two birthdays fall on the same day?**
Each is processed independently in the same run; there's no limit on
how many contacts can be matched in a single execution.

**Q: Can I track anniversaries or other recurring dates too?**
Not in this version - the CSV schema and matching logic are scoped to
birthdays only, per the current dataset design (`Name`, `PhoneNumber`,
`Birthday`, `Classification`, `Brief`, `Address`). Adding another
recurring-date type would be a schema change (see
`ARCHITECTURE.md → Future Improvements`).

**Q: How do I stop a specific person from getting messages without
deleting their row?**
Set their `Enabled` column to `FALSE`.

**Q: How do I test without sending a real SMS?**
Run the workflow manually via **Actions → Daily Birthday SMS → Run
workflow** with `dry_run` set to `true`, or set `DRY_RUN=true` when
running `python -m birthday_sms.main` locally.

**Q: Where are phone numbers validated?**
In `csv_reader.py`/`validator.py`, using a simplified E.164 check
(leading `+`, country code, 8-15 digits total). Numbers that fail this
check are logged and skipped, not silently sent to an invalid
destination.

**Q: Can I customize the message per person?**
Yes - leave the CSV's `MessageTemplate` column blank to use the
default template, or fill it in per-row with any combination of
`{NAME}`, `{FIRST_NAME}`, `{TODAY}`, `{YEAR}`, `{AGE}`,
`{CLASSIFICATION}`, `{BRIEF}`.

**Q: What timezone is "today" evaluated in?**
Whatever `BIRTHDAY_TIMEZONE` is set to (default `Asia/Kolkata`), not
the GitHub Actions runner's UTC clock. See `date_utils.py`.

**Q: Does SMS Gateway use WebSockets or FCM to communicate with the phone?**
It uses **Firebase Cloud Messaging (FCM)** push notifications. FCM allows the Cloud API to wake up the app on demand via Google Play Services without keeping a battery-heavy WebSocket connection open 24/7.

**Q: What is the difference between FCM and Webhooks in this setup?**
FCM handles the **Cloud → Phone** leg (triggering the Android app to send an SMS), whereas Webhooks (HTTPS POST requests) handle the **Cloud → Your Backend** leg (notifying your custom server of status events like `sms:sent`, `sms:delivered`, or `sms:failed`).

**Q: How do I know a message was actually delivered?**
After sending, the script polls the Cloud API (`GET /messages/{id}`)
for up to 10 minutes (configurable via `DELIVERY_POLL_WINDOW_SECONDS`).
The result — `Delivered`, `Failed`, or still unconfirmed — is shown in
the run logs and on the workflow run's **Summary** page.

**Q: What happens if the recipient's phone is switched off overnight?**
The SMS is queued on the cloud side and delivered when the phone comes
back online. The script records the message as *unconfirmed* in
`data/.sent_state.json` and re-checks it once at the start of the next
run, logging the final outcome then. Nobody is double-texted.

**Q: What license is this project under?**
MIT - see `LICENSE`.
