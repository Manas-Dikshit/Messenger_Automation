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
up every night at 23:50 IST (18:20 UTC), checks whether anyone's
birthday is about to begin, and - if so - waits until exactly
00:00 IST before sending, then commits the updated sent-state file -
all without the PC or the repository owner doing anything. On nights
with no birthdays, the run exits within seconds instead of waiting.

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
