# Troubleshooting

## Workflow fails immediately with "CONFIGURATION ERROR"

**Cause:** `SMS_GATEWAY_USERNAME` or `SMS_GATEWAY_PASSWORD` is not set.

**Fix:** Confirm both secrets exist under **Settings → Secrets and
variables → Actions → Secrets**, spelled exactly as shown (case
sensitive), and that `daily.yml`'s `env:` block references
`${{ secrets.SMS_GATEWAY_USERNAME }}` / `${{ secrets.SMS_GATEWAY_PASSWORD }}`.

## Logs show `SmsGatewayAuthenticationError`

**Cause:** Wrong username/password, or credentials were regenerated in
the app without updating the GitHub Secret.

**Fix:** Re-check the credentials in the app (Settings → Cloud Server
→ 3rd party API), update the GitHub Secrets to match, re-run.

## Logs show `SmsGatewayUnavailableError` / `RetryExhaustedError`

**Cause:** The teacher's phone is offline, has no internet connection,
or the Cloud Server connection was disabled/killed by battery
optimization.

**Fix:**
1. Check the phone is on and connected to Wi-Fi or mobile data.
2. Open the app and confirm it shows "Connected" for Cloud Server.
3. Re-check battery optimization settings (see
   [`SMS_GATEWAY_SETUP.md`](SMS_GATEWAY_SETUP.md) Section 3).
4. Manually re-run the workflow (`workflow_dispatch`) once the phone
   is back online - since the failed contact was never marked as
   sent, it will be retried automatically.

## CSV rows are silently skipped

**Cause:** Rows with an empty `Name`/`PhoneNumber`, an invalid phone
number, or an unparseable `Birthday` are logged as warnings and
skipped intentionally, so one bad row doesn't block everyone else.

**Fix:** Check the **Run birthday SMS script** step logs for lines
like `Skipping CSV row due to error: Row 4: ...` - they name the exact
row and reason. Fix that row in `data/birthdays.csv`.

## A contact didn't get a message even though today is their birthday

Check, in order:
1. Is their `Enabled` column `TRUE`? (blank also counts as enabled)
2. Does `data/.sent_state.json` already contain an entry for
   `<their phone>:<this year>`? If so, they were already messaged
   earlier today (or the workflow ran twice).
3. Did their row fail CSV validation? Check the logs (see above).
4. Is `BIRTHDAY_TIMEZONE` set correctly? A birthday can appear to be
   "tomorrow" or "yesterday" if the timezone doesn't match the
   contacts' actual local dates.

## Workflow didn't run at the scheduled time at all

GitHub Actions documents that scheduled workflows can be delayed
during periods of high platform load, and schedules are **disabled
automatically after 60 days of repository inactivity** (no commits).
Push any commit, or manually trigger the workflow once, to reactivate
scheduled runs.

## `curl` test from `SMS_GATEWAY_SETUP.md` works, but GitHub Actions doesn't

This almost always means the secret values in GitHub don't exactly
match what you tested locally (extra whitespace, wrong secret name,
or the secret was set at the environment level instead of repository
level). Re-copy the values carefully and re-save the secrets.

## Tests fail locally with `MissingSecretError`

Some tests exercise `AppConfig.from_env()`, which requires
`SMS_GATEWAY_USERNAME`/`SMS_GATEWAY_PASSWORD` to be present as
environment variables (dummy values are fine for tests - no network
calls are made). Set them before running pytest:

```bash
export SMS_GATEWAY_USERNAME=test
export SMS_GATEWAY_PASSWORD=test
pytest
```

(The `lint.yml` CI workflow already sets these automatically.)

## Still stuck?

Re-run the failing workflow with `dry_run: true` via
**Actions → Daily Birthday SMS → Run workflow** to isolate whether the
issue is in message rendering (dry run still exercises this) versus
the actual network call to the gateway (skipped in dry run).
