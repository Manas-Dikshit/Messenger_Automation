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
    """Reads/writes a small JSON file of `"<phone>:<year>": true` entries."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._data: dict[str, bool] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._data = {}
            return
        try:
            self._data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read state file (%s); starting fresh.", exc)
            self._data = {}

    def already_sent(self, phone_number: str, year: int) -> bool:
        return self._data.get(self._key(phone_number, year), False)

    def mark_sent(self, phone_number: str, year: int) -> None:
        self._data[self._key(phone_number, year)] = True

    def save(self) -> None:
        """Write the state file atomically (temp file + rename) so a crash
        mid-write can never leave a truncated/corrupt file behind - that
        would otherwise be silently treated as "empty" on the next run
        (see `_load`), risking a duplicate SMS to everyone.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._data, indent=2, sort_keys=True)

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
