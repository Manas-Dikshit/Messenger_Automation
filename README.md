# Birthday SMS Automation

Automatically sends a Birthday SMS to people on a contact list — from
a teacher's **own Android phone and SIM card** — every year, with no
PC left running, no cloud SMS provider, and no business API.

```
GitHub Actions  --daily cron-->  Python script  --HTTPS-->  SMS Gateway Cloud API
                                                                  |
                                                                  v
                                                   SMS Gateway for Android app
                                                                  |
                                                                  v
                                                        Teacher's SIM --> Recipient
```

Full architecture, diagrams, and design rationale: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Table of Contents

- [Why this project exists](#why-this-project-exists)
- [Features](#features)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [CSV Format](#csv-format)
- [Message Templates](#message-templates)
- [Configuration Reference](#configuration-reference)
- [Folder Structure](#folder-structure)
- [Example API Request](#example-api-request)
- [Testing](#testing)
- [Documentation Index](#documentation-index)
- [Contributing](#contributing)
- [License](#license)

## Why This Project Exists

Bulk SMS APIs (Twilio, MSG91, TextLocal, etc.) charge per message,
require sender-ID registration, and send from a number the recipient
doesn't recognize. This project instead automates the exact thing a
teacher would otherwise do by hand: text a student "Happy Birthday"
from their own phone — just automatically, every day, forever, without
anyone needing to remember to do it.

## Features

- ✅ Sends real SMS from the teacher's own SIM (no bulk SMS API)
- ✅ Fully automated via GitHub Actions — no server or PC required
- ✅ CSV-driven contact list, editable directly on GitHub
- ✅ Placeholder-based message templates (`{NAME}`, `{FIRST_NAME}`, `{AGE}`, ...)
- ✅ Per-contact custom message override
- ✅ Duplicate-send protection (won't text the same person twice in a day)
- ✅ Automatic retry with exponential backoff for transient network errors
- ✅ Structured logging visible directly in the GitHub Actions log viewer
- ✅ `dry_run` mode to test message rendering without sending real SMS
- ✅ Type-hinted, tested, linted Python 3.12+ codebase

## Requirements

- A GitHub repository (private recommended if the CSV holds real data)
- An Android phone with a SIM plan capable of sending SMS
- [SMS Gateway for Android](https://sms-gate.app) (capcom6, open source) installed on that phone, in **Cloud Mode**
- Python 3.12+ (only needed for local testing — GitHub Actions installs it automatically for scheduled runs)

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Manas-Dikshit/Messenger_Automation.git
cd birthday-sms-automation

# 2. (Optional) local dependency install for testing
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .

# 3. Configure local env for testing (never commit this file)
cp .env.example .env
```

Then:
1. Set up the Android app: [`docs/SMS_GATEWAY_SETUP.md`](docs/SMS_GATEWAY_SETUP.md)
2. Add GitHub Secrets: [`docs/SECURITY.md`](docs/SECURITY.md)
3. Edit `data/birthdays.csv` with your contacts
4. Push to GitHub — the `daily.yml` workflow takes it from there

Full walkthrough: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## CSV Format

File: `data/birthdays.csv`. Header row required. Only **birthdays**
are tracked — there is intentionally no anniversary/wedding-day field.

| Column | Required | Description |
|---|---|---|
| `Name` | ✅ | Full name |
| `PhoneNumber` | ✅ | E.164 format, e.g. `+919876543210` |
| `Birthday` | ✅ | `YYYY-MM-DD` preferred (also accepts `DD-MM-YYYY`, `DD/MM/YYYY`, `MM/DD/YYYY`) |
| `Classification` | – | Free text, e.g. `Student`, `Colleague`, `Class 10 - Section B` |
| `Brief` | – | Short note, e.g. section/department |
| `Address` | – | Free text |
| `Enabled` | – | `TRUE`/`FALSE` — set `FALSE` to pause messages to this contact without deleting the row. Blank = enabled |
| `LastSent` | – | Informational only; actual dedupe state lives in `data/.sent_state.json` |
| `MessageTemplate` | – | Per-contact override of the default message template |

Example:

```csv
Name,PhoneNumber,Birthday,Classification,Brief,Address,Enabled,LastSent,MessageTemplate
Rahul Sharma,+919876543210,1999-05-16,Student,Class 10 - Section B,"12 MG Road, Kolkata",TRUE,,
```

## Message Templates

Supported placeholders, substituted safely (unknown placeholders are
left untouched rather than crashing the run):

| Placeholder | Renders as |
|---|---|
| `{NAME}` | Full name |
| `{FIRST_NAME}` | First word of the name |
| `{TODAY}` | Today's date, `YYYY-MM-DD` |
| `{YEAR}` | Current year |
| `{AGE}` | Age the contact is turning today |
| `{CLASSIFICATION}` | The `Classification` column |
| `{BRIEF}` | The `Brief` column |

Default template (overridable via `DEFAULT_MESSAGE_TEMPLATE` env var
or the `daily.yml` workflow env block):

```
Happy Birthday {FIRST_NAME}! 🎉 Wishing you a wonderful year ahead. - From your teacher
```

## Configuration Reference

All configuration is via environment variables — see
[`.env.example`](.env.example) for the full list with defaults. Key
ones:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `SMS_GATEWAY_USERNAME` | ✅ | — | GitHub Secret |
| `SMS_GATEWAY_PASSWORD` | ✅ | — | GitHub Secret |
| `SMS_GATEWAY_BASE_URL` | – | `https://api.sms-gate.app/3rdparty/v1` | Only change for self-hosted relays |
| `BIRTHDAY_CSV_PATH` | – | `data/birthdays.csv` | |
| `BIRTHDAY_TIMEZONE` | – | `Asia/Kolkata` | IANA timezone name |
| `SMS_GATEWAY_MAX_RETRIES` | – | `4` | Exponential backoff |
| `SMS_GATEWAY_TIMEOUT_SECONDS` | – | `15` | Per-request timeout |
| `DRY_RUN` | – | `false` | Render but don't send |
| `LOG_LEVEL` | – | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR` |

## Folder Structure

See the full annotated tree in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#8-folder-structure).

```
birthday-sms-automation/
├── .github/workflows/   # daily.yml (scheduler) + lint.yml (CI)
├── data/                # birthdays.csv + auto-managed sent-state
├── docs/                # architecture, security, setup, deployment, FAQ
├── src/birthday_sms/    # application source
├── tests/                # pytest suite
└── README.md
```

## Example API Request

What this project sends to the SMS Gateway Cloud API under the hood
(see `sms_gateway_client.py`):

```bash
curl -u "$SMS_GATEWAY_USERNAME:$SMS_GATEWAY_PASSWORD" \
  -X POST "https://api.sms-gate.app/3rdparty/v1/messages" \
  -H "Content-Type: application/json" \
  -d '{
        "message": "Happy Birthday Rahul! Wishing you a wonderful year ahead. - From your teacher",
        "phoneNumbers": ["+919876543210"]
      }'
```

## Testing

```bash
export SMS_GATEWAY_USERNAME=test
export SMS_GATEWAY_PASSWORD=test
pytest --cov=birthday_sms --cov-report=term-missing
```

Tests cover CSV parsing/validation, date parsing, message rendering,
retry/backoff behavior against a mocked HTTP layer (no real network
calls), and the full send orchestration logic.

## Troubleshooting & FAQ

- Common errors and fixes: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)
- Frequently asked questions: [`docs/FAQ.md`](docs/FAQ.md)
- Updating credentials, migrating phones: [`docs/SMS_GATEWAY_SETUP.md`](docs/SMS_GATEWAY_SETUP.md)

## Documentation Index

| Document | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design, diagrams, tech stack, failure scenarios, versioning |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Threat model, secrets handling, credential rotation/revocation |
| [`docs/SMS_GATEWAY_SETUP.md`](docs/SMS_GATEWAY_SETUP.md) | Android app installation, permissions, Cloud Mode setup |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Step-by-step from clone to fully running system |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Symptom → cause → fix reference |
| [`docs/FAQ.md`](docs/FAQ.md) | Common questions |
| [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) | Dev setup, style, PR process |

## Contributing

See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

## License

[MIT](LICENSE) — "SMS Gateway for Android" is a trademark/product of
its respective author (capcom6); this project is an independent
integration and is not affiliated with or endorsed by it.
