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

## Run summary says a delivery is "unconfirmed"

The message was accepted by the cloud gateway but hadn't reached
`Delivered` state before the polling window closed (default 10
minutes, `DELIVERY_POLL_WINDOW_SECONDS`). The most common cause is
the recipient's phone being switched off — the SMS is delivered
automatically once it comes back online. The script re-checks
unconfirmed messages at the start of the next run and logs the final
outcome; nothing is re-sent, so there is no duplicate risk. If a
message stays unconfirmed for several days, check the number and the
SMS Gateway app's own log on the phone.

## Run summary says a delivery "Failed"

The gateway (or carrier) reported the SMS as undeliverable. Verify
the phone number in `data/birthdays.csv`, and check the SMS Gateway
app's log on the sending phone for carrier errors. Note the dedupe
state was already marked, so fixing the number and re-running the
workflow the same day will skip that contact — remove their
`<phone>:<year>` entry from `data/.sent_state.json` first if you want
an immediate resend.

## Workflow didn't run at the scheduled time at all

GitHub Actions documents that scheduled workflows can be delayed
during periods of high platform load, and schedules are **disabled
automatically after 60 days of repository inactivity** (no commits).
Push any commit, or manually trigger the workflow once, to reactivate
scheduled runs.

The 60-day disable is handled automatically by
[`.github/workflows/keepalive.yml`](../.github/workflows/keepalive.yml),
which commits a small heartbeat timestamp
(`.github/.keepalive`) on the 1st and 15th of every month - well
inside the 60-day window - so `daily.yml`'s `schedule:` trigger never
goes quiet even if there are no birthdays or manual pushes for a long
stretch. (`cron_ping.yml` has no `schedule:` trigger at all - see
below - so the 60-day rule doesn't apply to it.) If schedules still
appear disabled, check that the keepalive workflow itself is running
(Actions → Repo Keepalive) and actually producing commits.

For the more common case - the trigger fired, but late by minutes to
hours - that's expected GitHub behavior with no fix on this project's
side; see the Limitations section in
[`ARCHITECTURE.md`](ARCHITECTURE.md#13-limitations) and consider the
external-scheduler setup in
[`DEPLOYMENT.md`](DEPLOYMENT.md#step-9b---recommended-external-scheduler-for-on-time-triggers)
if on-time delivery matters.

## `cron_ping.yml` never runs on its own

By design - it has no `schedule:` trigger (no dedupe logic, so a
double-fire would be a real duplicate API call, not just wasted
compute). It only runs via `workflow_dispatch` - manually, or through
an external scheduler like cron-job.org. If it's not firing daily,
check that your cron-job.org job (or equivalent) is configured and
its execution history shows successful calls.

## cron-job.org's test run returns 404 or "Unauthorized"

Common causes, in order of likelihood:

1. **Request method not set to POST** - GitHub's dispatch endpoint
   returns 404 for any other method, including the default GET some
   UIs silently start with. Explicitly select POST.
2. **`Authorization` header malformed** - must be exactly
   `Bearer <token>` (literal word "Bearer", one space, then the
   token) - a missing "Bearer " prefix or extra whitespace causes
   "Unauthorized."
3. **"Requires HTTP authentication" toggle enabled** (a separate
   Basic-Auth feature, not what we use) with empty username/password
   - can cause a generic "non-well-formed job" error. Turn it off;
   authentication happens via the custom header instead.
4. **Token lacks the `Actions: Read and write` permission**, or was
   scoped to the wrong repository.

Isolate the problem by testing the exact same request from your own
terminal first:
```bash
curl -i -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -H "Content-Type: application/json" \
  -d '{"ref":"main"}' \
  https://api.github.com/repos/<owner>/<repo>/actions/workflows/daily.yml/dispatches
```
Expect `HTTP/1.1 204 No Content`. If this works but cron-job.org
doesn't, the problem is in cron-job.org's saved configuration, not
the token or GitHub's side.

## A workflow file shows as `.github/workflows/name.yml #N` instead of its proper name, and fails instantly

This means GitHub couldn't parse the workflow file at all (a startup
failure, not a job failure) - it falls back to showing the raw path
since it can't read the `name:` field. `yaml.safe_load()` won't catch
this, since it only validates generic YAML syntax, not GitHub
Actions' schema rules (e.g. `secrets.*` is not a valid context inside
a step's `if:` condition - this exact bug broke both workflows in
production for ~2.5 hours before being caught). Run
[`actionlint`](https://github.com/rhysd/actionlint) locally
(`pip install actionlint-py && actionlint .github/workflows/*.yml`)
to catch this before pushing - it's also enforced in CI via
`lint.yml`, so a PR with this class of bug should fail before merge.

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
