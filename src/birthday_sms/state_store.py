"""Tracks which contacts already received a birthday SMS this year.

GitHub Actions runners are stateless between runs, so persistence
relies on this JSON file being committed back to the repository by
the workflow after each run (see `.github/workflows/daily.yml`). This
guards against duplicate sends if the workflow is re-run manually on
the same day, or if the schedule fires more than once.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class SentStateStore:
    """Reads/writes a small JSON state file.

    File layout (current):

        {
          "sent": {"<phone>:<year>": true, ...},
          "unconfirmed": {"<message_id>": {"phone": "...", "year": 2026}, ...}
        }

    Legacy files were a flat `{"<phone>:<year>": true}` mapping; those
    are migrated transparently on load.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._sent: dict[str, bool] = {}
        self._unconfirmed: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read state file (%s); starting fresh.", exc)
            return

        if isinstance(raw, dict) and "sent" in raw:
            self._sent = dict(raw.get("sent") or {})
            self._unconfirmed = dict(raw.get("unconfirmed") or {})
        elif isinstance(raw, dict):
            # Legacy flat format: every key is "<phone>:<year>" -> bool.
            self._sent = raw

    def already_sent(self, phone_number: str, year: int) -> bool:
        return self._sent.get(self._key(phone_number, year), False)

    def mark_sent(self, phone_number: str, year: int) -> None:
        self._sent[self._key(phone_number, year)] = True

    def mark_unconfirmed(self, message_id: str, phone_number: str, year: int) -> None:
        """Record a sent message whose delivery was not confirmed this run."""
        self._unconfirmed[message_id] = {"phone": phone_number, "year": year}

    def resolve_unconfirmed(self, message_id: str) -> None:
        """Remove a message from the unconfirmed list (reached terminal state)."""
        self._unconfirmed.pop(message_id, None)

    def unconfirmed(self) -> dict[str, dict]:
        """Return a copy of the unconfirmed message map."""
        return dict(self._unconfirmed)

    def save(self) -> None:
        """Write the state file atomically (temp file + rename) so a crash
        mid-write can never leave a truncated/corrupt file behind - that
        would otherwise be silently treated as "empty" on the next run
        (see `_load`), risking a duplicate SMS to everyone.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"sent": self._sent, "unconfirmed": self._unconfirmed},
            indent=2,
            sort_keys=True,
        )

        fd, tmp_name = tempfile.mkstemp(
            dir=self._path.parent, prefix=f".{self._path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                tmp_file.write(payload)
            os.replace(tmp_name, self._path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    @staticmethod
    def _key(phone_number: str, year: int) -> str:
        return f"{phone_number}:{year}"
