# Deployment Guide

This walks through going from a fresh clone to a fully automated,
running system.

## Step 1 - Set Up the Android App

Complete every step in [`SMS_GATEWAY_SETUP.md`](SMS_GATEWAY_SETUP.md)
first. You need working Cloud Mode credentials before continuing.

## Step 2 - Get the Code

```bash
git clone https://github.com/<your-username>/birthday-sms-automation.git
cd birthday-sms-automation
```

Or, if starting from this generated project locally, push it to a new
GitHub repository:

```bash
git init
git add .
git commit -m "Initial commit: Birthday SMS Automation"
git branch -M main
git remote add origin https://github.com/<your-username>/birthday-sms-automation.git
git push -u origin main
```

**Make the repository Private** if `data/birthdays.csv` will contain
real names, phone numbers, or addresses (Settings → General →
Danger Zone → Change repository visibility).

## Step 3 - Install Dependencies (local testing, optional)

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
```

## Step 4 - Configure Local Environment (optional, for testing)

```bash
cp .env.example .env
# edit .env and fill in SMS_GATEWAY_USERNAME / SMS_GATEWAY_PASSWORD
```

Run a dry run locally (renders messages, does not send real SMS):

```bash
set -a; source .env; set +a
DRY_RUN=true python -m birthday_sms.main
```

## Step 5 - Configure GitHub Secrets

In the repository on GitHub:

1. **Settings → Secrets and variables → Actions → Secrets** tab:
   - `SMS_GATEWAY_USERNAME`
   - `SMS_GATEWAY_PASSWORD`
2. **Settings → Secrets and variables → Actions → Variables** tab
   (optional, non-sensitive overrides):
   - `BIRTHDAY_TIMEZONE` = `Asia/Kolkata` (or your timezone)
   - `SMS_GATEWAY_BASE_URL` (only if self-hosting)

Full details in [`SECURITY.md`](SECURITY.md).

## Step 6 - Upload / Edit the Contact CSV

Edit `data/birthdays.csv` directly on GitHub (click the file → pencil
icon → edit) or locally and push. Required columns: `Name`,
`PhoneNumber`, `Birthday`. See the [README's CSV section](../README.md#csv-format)
for the full schema and examples.

Commit and push:

```bash
git add data/birthdays.csv
git commit -m "Update birthday contact list"
git push
```

## Step 7 - Enable the Workflow

Workflows are enabled automatically once `.github/workflows/daily.yml`
is pushed to the default branch. Confirm it's active:

1. Go to the **Actions** tab on GitHub.
2. You should see **Daily Birthday SMS** listed as a workflow.
3. Click it, then **Run workflow** (top right) to trigger a manual
   test run. Set `dry_run` to `true` for the first test.

## Step 8 - Verify

1. Watch the run under **Actions → Daily Birthday SMS → (latest run)**.
2. Expand the **Run birthday SMS script** step to see structured logs:
   contacts loaded, birthdays found (or not, depending on today's
   date), and the outcome of each.
3. For a real (non-dry-run) test, temporarily set a test contact's
   `Birthday` in the CSV to today's date, run the workflow manually
   with `dry_run: false`, confirm the SMS arrives, then revert the CSV
   change.

## Step 9 - Let It Run

From here, no further action is needed. The `daily.yml` workflow wakes
up shortly after midnight, at 00:10 IST (18:40 UTC), checks whether
anyone's birthday is today, and sends immediately if so, then commits
the updated sent-state file - all without the PC or the repository
owner doing anything. On nights with no birthdays, the run exits
within seconds. Note GitHub does not guarantee this trigger fires
exactly on time - see the Limitations section in
[`ARCHITECTURE.md`](ARCHITECTURE.md#13-limitations) for how much it
can actually drift.

## Step 9b - (Recommended) External Scheduler for On-Time Triggers

GitHub's own `schedule:` trigger has no timing guarantee and can be
delayed by minutes to hours, or occasionally dropped, especially
during high-load periods. `workflow_dispatch` (manual, or via API),
by contrast, runs promptly - it's the same trigger used by the "Run
workflow" button.

[cron-job.org](https://cron-job.org) (free) is used to call GitHub's
`workflow_dispatch` API on a precise schedule, so the actual trigger
time no longer depends on GitHub's scheduling queue:

1. Create a GitHub fine-grained Personal Access Token: **Settings →
   Developer settings → Personal access tokens → Fine-grained
   tokens**. Scope it to only this repository, with **Actions: Read
   and write** permission - nothing else.
2. Sign up at [cron-job.org](https://cron-job.org).
3. Create a cronjob:
   - URL: `https://api.github.com/repos/<owner>/<repo>/actions/workflows/daily.yml/dispatches`
   - Request method: **POST**
   - Schedule: "Every day at" the same time as your `daily.yml` cron
     (in UTC)
   - Headers: `Authorization: Bearer <token>`,
     `Accept: application/vnd.github+json`,
     `Content-Type: application/json`,
     `X-GitHub-Api-Version: 2022-11-28`
   - Request body: `{"ref":"main"}`
4. Test with cron-job.org's **Test run** button - a `204` response
   means success; check the Actions tab for a new `workflow_dispatch`
   run.

GitHub's own `schedule:` cron is left in place as a free backup - if
cron-job.org ever fails to fire, GitHub's (slower, but eventually
working) scheduler still catches it. The dedupe logic in
`state_store.py` means there's no risk of a duplicate SMS if both
happen to fire the same day.

**Note:** `cron_ping.yml` has no dedupe logic, so it intentionally has
**no** `schedule:` trigger at all - only `workflow_dispatch`, so it
must be driven entirely by an external scheduler like cron-job.org
to run daily. Running it twice would be a real duplicate API call,
not just wasted compute.

A separate `.github/workflows/keepalive.yml` runs twice a month and
commits a small heartbeat file for one reason only: GitHub disables
scheduled workflows after 60 days without a commit to the repo, and
this guarantees that never happens even during long stretches with no
birthdays. No action needed - it's fully automatic.

After sending, the run polls the gateway for delivery confirmation
(up to 10 minutes) and writes a Markdown report — status counts,
per-contact delivery outcome, and any unconfirmed messages — to the
workflow run's **Summary** page (Actions → the run → Summary).
Messages that stay unconfirmed (recipient's phone off) are re-checked
automatically at the start of the next run.

## Updating Things Later

- **Add/remove a contact:** edit `data/birthdays.csv`, commit, push.
- **Change the default message:** edit `DEFAULT_MESSAGE_TEMPLATE` in
  the `daily.yml` env block, or set a per-contact `MessageTemplate` in
  the CSV.
- **Change send time:** edit the `cron` line in
  `.github/workflows/daily.yml` (remember: cron is UTC).
- **Rotate/revoke credentials:** see [`SECURITY.md`](SECURITY.md).
- **Move to a new phone:** see the "Migrating to a New Phone" section
  in [`SMS_GATEWAY_SETUP.md`](SMS_GATEWAY_SETUP.md).
