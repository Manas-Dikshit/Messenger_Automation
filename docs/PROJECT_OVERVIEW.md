# Project Overview — Birthday SMS Automation

## What This Project Does

Every day, this project checks a list of contacts (name, phone
number, birthday) and — if it's someone's birthday — sends them a
personalized SMS wishing them a happy birthday. The message is sent
right at **midnight**, from a **real phone's SIM card** (not a bulk
SMS service), so it looks and feels like the sender personally
texted them at the stroke of midnight.

Think of it as: "a teacher/professor who never forgets a birthday,
because a script remembers for them."

## Who It's For

Originally built for a teacher to auto-wish students and colleagues
on their birthdays. Easily reused for any group: a club, a family, a
professional association (in this deployment: Rotarian club members)
— anyone with a phone number and a birthday.

## Why It's Built This Way

Most "bulk SMS" services (Twilio, MSG91, etc.) have problems for
this use case:
- They charge per message.
- The recipient sees an unfamiliar sender ID/number, not the actual
  person.
- They require business registration and API contracts.

Instead, this project automates the exact action a person would do
by hand — open their own phone, type a birthday text, hit send — just
on a schedule, forever, without anyone needing to remember.

## How It Works (High Level)

```
GitHub Actions (free, scheduled)
        │  runs daily just after midnight
        ▼
Python script
        │  reads contacts from a CSV file
        │  checks whose birthday is today
        │  renders a message from a template
        ▼
SMS Gateway for Android (free, open-source app)
        │  running in "Cloud Mode" on the sender's own phone
        ▼
Sender's own SIM card → Recipient's phone
```

1. **The contact list** lives in `data/birthdays.csv` — a plain text
   file, editable directly on GitHub or in Excel. Columns: Name,
   PhoneNumber, Birthday, and a few optional extras (Classification,
   Brief, Address, Enabled, custom message override).

2. **The schedule** is a GitHub Actions workflow
   (`.github/workflows/daily.yml`) — GitHub's free automation runner,
   triggered by a cron schedule every day. No server, no PC that
   needs to stay on, no cost.

3. **The message engine** (`src/birthday_sms/`) is a small, tested
   Python application that:
   - Reads and validates the CSV.
   - Figures out whose birthday is today (comparing month + day only
     — birth year isn't required for the check itself).
   - Fills in a message template with placeholders like `{FIRST_NAME}`.
   - Sends the message and records that this person was already
     wished this year (so a re-run the same day doesn't double-send).

4. **The actual sending** happens through **SMS Gateway for Android**
   — a free, open-source Android app (by developer capcom6) that
   turns a phone into an SMS-sending API. The Python script calls
   this app's cloud API; the app relays the message out through the
   phone's own SIM and normal cellular network — exactly as if the
   phone's owner had typed and sent it themselves.

## What's in the Repository

| Path | Purpose |
|---|---|
| `data/birthdays.csv` | The contact list — the main thing you'll edit |
| `data/.sent_state.json` | Auto-managed "already sent this year" tracker |
| `src/birthday_sms/` | The Python application source code |
| `tests/` | Automated tests (pytest) covering every part of the logic |
| `.github/workflows/daily.yml` | The daily scheduler |
| `.github/workflows/lint.yml` | Code-quality checks that run on every change |
| `docs/` | All documentation (architecture, setup, security, FAQ, this file) |
| `.env.example` | Template for local configuration/testing |

## Key Design Choices Worth Knowing

- **No cloud SMS provider, no per-message cost.** Sending goes
  through a real SIM plan, same as sending a text by hand.
- **CSV-driven, not database-driven.** Anyone comfortable with Excel
  or a spreadsheet can maintain the contact list — no technical
  skill required for day-to-day use.
- **Dedupe protection.** The app keeps a small state file so nobody
  gets double-texted if the workflow happens to run twice in a day.
- **Delivery confirmation.** After sending, the app polls the gateway
  until each message is confirmed `Delivered` (or `Failed`). If the
  recipient's phone is off, the message is remembered as *unconfirmed*
  and checked again automatically on the next night's run. Each run's
  outcome appears as a report on the GitHub Actions Summary page.
- **Dry-run mode.** Every part of the system can be tested without
  sending a single real SMS (`DRY_RUN=true`), so changes can be
  verified safely before going live.
- **Per-contact overrides.** Any single contact's row can specify
  its own custom message template, or be temporarily disabled
  (`Enabled=FALSE`) without deleting their data.
- **Secrets stay out of the code.** The SMS Gateway login is stored
  as a GitHub Secret, never committed to the repository, never
  logged.

## Where to Go Next

- New to this project and want to get it running? → `docs/SETUP_GUIDE.md`
- Want the full technical architecture and failure-mode analysis? → `docs/ARCHITECTURE.md`
- Setting up the Android app itself? → `docs/SMS_GATEWAY_SETUP.md`
- Something broke? → `docs/TROUBLESHOOTING.md`
- Common questions? → `docs/FAQ.md`
- Security/secrets handling details? → `docs/SECURITY.md`
