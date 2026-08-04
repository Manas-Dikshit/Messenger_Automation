"""Single-purpose cron script: call one API endpoint, then exit.

Invoked by GitHub Actions as:

    python cron_ping/main.py

Configuration via environment variables (see .env.example):
    API_URL     - required, full endpoint URL to call
    API_KEY     - optional, sent as "Authorization: Bearer <API_KEY>" if set
    API_METHOD  - optional, "GET" or "POST" (default "GET")

Exit codes:
    0 - request succeeded (HTTP 2xx)
    1 - missing configuration or request failed
"""

import os
import sys

import requests

DEFAULT_TIMEOUT_SECONDS = 15


def main() -> int:
    url = os.environ.get("API_URL")
    api_key = os.environ.get("API_KEY")
    method = os.environ.get("API_METHOD", "GET").upper()

    if not url:
        print("CONFIGURATION ERROR: API_URL must be set.", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        print(f"REQUEST FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"{method} {url} -> HTTP {response.status_code}")
    print(response.text[:500])

    if response.status_code // 100 != 2:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
