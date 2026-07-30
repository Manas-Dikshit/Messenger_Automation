"""Central constants for the Birthday SMS Automation project.

Keeping constants in one place avoids magic strings/numbers scattered
across the codebase and makes the system easier to audit and tune.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# CSV schema
# --------------------------------------------------------------------------
# Column order and names expected in the contacts CSV file.
# NOTE: Only birthdays are tracked. There is intentionally no
# "anniversary" / "wedding day" column in this dataset.
CSV_COLUMN_NAME = "Name"
CSV_COLUMN_PHONE_NUMBER = "PhoneNumber"
CSV_COLUMN_BIRTHDAY = "Birthday"
CSV_COLUMN_CLASSIFICATION = "Classification"
CSV_COLUMN_BRIEF = "Brief"
CSV_COLUMN_ADDRESS = "Address"
CSV_COLUMN_ENABLED = "Enabled"
CSV_COLUMN_LAST_SENT = "LastSent"
CSV_COLUMN_MESSAGE_TEMPLATE = "MessageTemplate"

CSV_REQUIRED_COLUMNS: tuple[str, ...] = (
    CSV_COLUMN_NAME,
    CSV_COLUMN_PHONE_NUMBER,
    CSV_COLUMN_BIRTHDAY,
)

CSV_ALL_COLUMNS: tuple[str, ...] = (
    CSV_COLUMN_NAME,
    CSV_COLUMN_PHONE_NUMBER,
    CSV_COLUMN_BIRTHDAY,
    CSV_COLUMN_CLASSIFICATION,
    CSV_COLUMN_BRIEF,
    CSV_COLUMN_ADDRESS,
    CSV_COLUMN_ENABLED,
    CSV_COLUMN_LAST_SENT,
    CSV_COLUMN_MESSAGE_TEMPLATE,
)

# Accepted date formats for the Birthday column, tried in order.
SUPPORTED_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",  # 1999-05-16 (preferred, ISO 8601)
    "%d-%m-%Y",  # 16-05-1999
    "%d/%m/%Y",  # 16/05/1999
    "%m/%d/%Y",  # 05/16/1999
)

# --------------------------------------------------------------------------
# Message templating placeholders
# --------------------------------------------------------------------------
PLACEHOLDER_NAME = "{NAME}"
PLACEHOLDER_FIRST_NAME = "{FIRST_NAME}"
PLACEHOLDER_TODAY = "{TODAY}"
PLACEHOLDER_YEAR = "{YEAR}"
PLACEHOLDER_AGE = "{AGE}"
PLACEHOLDER_CLASSIFICATION = "{CLASSIFICATION}"
PLACEHOLDER_BRIEF = "{BRIEF}"

DEFAULT_MESSAGE_TEMPLATE = (
    "Happy Birthday to Rtn. {NAME}! 🎉🎂\n\n"
    "The members of Rotary Club, Burla extend our heartfelt wishes to you on your special day.\n\n"
    "Wishing you many, many happy returns of the day! May you be blessed with good health, happiness, success, "
    "and many more years of dedicated service to humanity through Rotary.\n\n"
    "With regards,\n"
    "Dr. Rasmikanta Pati, Asst. Professor, Mathematics\n"
    "SUIIT, Sambalpur University\n"
    "Sambalpur, Odisha-768019"
)

# --------------------------------------------------------------------------
# Networking / retry defaults (overridable via environment variables)
# --------------------------------------------------------------------------
DEFAULT_API_TIMEOUT_SECONDS = 15
DEFAULT_MAX_RETRIES = 4
DEFAULT_RETRY_BACKOFF_BASE_SECONDS = 2.0
DEFAULT_RETRY_BACKOFF_MAX_SECONDS = 30.0

# HTTP status codes considered transient / worth retrying.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})

# SMS Gateway for Android (capcom6) Cloud Mode API defaults.
DEFAULT_SMS_GATEWAY_BASE_URL = "https://api.sms-gate.app/3rdparty/v1"
SMS_GATEWAY_MESSAGES_ENDPOINT = "/messages"

# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------
DEFAULT_TIMEZONE = "Asia/Kolkata"
DEFAULT_CSV_PATH = "data/birthdays.csv"
DEFAULT_LOG_LEVEL = "INFO"
STATE_FILE_PATH = "data/.sent_state.json"
