#!/usr/bin/env python3
"""
birthday_sms.validate_and_sync_csv

Validates a Google-Sheets-exported birthdays CSV *before* it is allowed to
replace the repository's data/birthdays.csv, then performs an idempotent
sync (copy + diff summary + GitHub Actions outputs/summary).

This module lives inside the birthday_sms package (rather than a
standalone scripts/ dir) so it can import CsvContactRepository as a normal
in-package absolute import. It is invoked as a module, not as a loose
script:

    python -m birthday_sms.validate_and_sync_csv --source <tmp.csv> --target data/birthdays.csv

It has no CLI dependency on the rest of the app beyond CsvContactRepository
itself, and isn't imported by any other birthday_sms module - it won't
affect `python -m birthday_sms.main` or anything else at runtime.

Reuse policy
------------
Row-level parsing/validation (required fields, phone E.164 format, date
format per the four supported formats) is delegated entirely to the
project's own `birthday_sms.csv_reader.CsvContactRepository.load()` - no
duplicated parsing logic. That method skips-and-logs bad rows rather than
raising, so this script attaches a temporary logging handler to
"birthday_sms.csv_reader" to capture the exact skip reasons it already
produces, and treats "the real parser had to skip anything" as a sync
validation failure (stricter than runtime behaviour, which is intentional:
at runtime one bad contact shouldn't block everyone else's SMS, but the
*sync* gate should refuse to silently promote a sheet with rows the app
can't fully parse).

On top of that reuse, this script adds checks the application layer
doesn't need at runtime but a sync gate does:
  - required *headers* existing at all (Name, PhoneNumber, Birthday,
    Classification, Enabled) - independent of per-row value validation
  - duplicate phone numbers across the whole file
  - at least one valid, enabled recipient
  - basic file-level sanity (non-empty, parseable CSV, no
    structurally malformed rows - wrong field count per row)

If `birthday_sms` isn't importable in the environment this script runs in,
it falls back to an equivalent standalone validator so the script still
works in isolation (e.g. unit tests). In the real CI job, `pip install -e .`
is run before this script, so the reuse path is what actually executes.

Exit codes
----------
0 - validation passed (file may or may not have changed - see `changed`
    output)
1 - validation failed (data/birthdays.csv was NOT touched)

GitHub Actions integration
---------------------------
Writes a Markdown report to $GITHUB_STEP_SUMMARY (falls back to stdout if
unset) and sets `valid`, `changed`, `total`, `enabled`, `disabled`, `added`,
`removed`, `modified` in $GITHUB_OUTPUT (falls back to stdout if unset).
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REQUIRED_HEADERS = ["Name", "PhoneNumber", "Birthday", "Classification", "Enabled"]
DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"]  # fallback-only; real
# parsing uses birthday_sms.date_utils.parse_date via CsvContactRepository.
EXTRA_FIELDS_KEY = "__extra_fields__"


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    message: str
    row_number: Optional[int] = None  # 1-indexed, header row = 1
    field: Optional[str] = None

    def format(self) -> str:
        loc = ""
        if self.row_number is not None:
            loc = f"Row {self.row_number}"
            if self.field:
                loc += f", field `{self.field}`"
            loc += ": "
        return f"{loc}{self.message}"


@dataclass
class ValidationResult:
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    rows: List[Dict[str, str]] = field(default_factory=list)
    fieldnames: List[str] = field(default_factory=list)
    total: int = 0
    enabled: int = 0
    disabled: int = 0
    reused_project_parser: bool = False


# --------------------------------------------------------------------------
# Google Sheets auto-formatting corruption detection
#
# If the PhoneNumber (or Birthday) column in the Sheet isn't set to
# "Plain text", Google Sheets silently reinterprets values that look
# numeric/date-like and reformats them - the CSV export then contains
# the *reformatted* value, not what was actually typed. This is a data
# problem in the sheet, not a validation bug, but it's common enough
# (and confusing enough - "my phone numbers are showing different")
# that it's worth detecting explicitly and pointing at the real fix
# rather than surfacing a generic "not valid E.164" error.
# --------------------------------------------------------------------------

_SCIENTIFIC_NOTATION_RE = re.compile(r"^-?\d+(\.\d+)?[eE][+-]?\d+$")
_BARE_LONG_DIGIT_RE = re.compile(r"^\d{10,15}$")  # all-digit, no '+', plausible phone length


def _sheets_corruption_hint(raw_phone: str) -> Optional[str]:
    """Return a human-readable hint if a raw PhoneNumber value looks like
    Google Sheets silently reformatted it as a number, or None otherwise."""
    value = (raw_phone or "").strip()
    if not value:
        return None

    if _SCIENTIFIC_NOTATION_RE.match(value):
        return (
            f"PhoneNumber {value!r} looks like Google Sheets auto-converted it to a "
            f"number (scientific notation) instead of keeping it as text. Fix: in "
            f"the Sheet, select the PhoneNumber column, Format → Number → Plain text, "
            f"then re-enter the numbers (or prefix each with an apostrophe, e.g. "
            f"'+919876543210), and republish."
        )

    if _BARE_LONG_DIGIT_RE.match(value):
        return (
            f"PhoneNumber {value!r} has no leading '+' and looks like Google Sheets "
            f"stripped it by treating the cell as a number (this can also drop "
            f"leading zeros). Fix: format the PhoneNumber column as Plain text in "
            f"the Sheet (Format → Number → Plain text) before re-entering numbers, "
            f"then republish."
        )

    return None


def _read_raw(path: Path) -> Tuple[List[str], List[Dict[str, object]], List[ValidationIssue]]:
    """Read the CSV with csv.DictReader, flagging structurally malformed rows
    (wrong number of fields). Fully blank trailing lines (common in
    Sheets/Excel exports) are ignored rather than flagged."""
    issues: List[ValidationIssue] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        try:
            reader = csv.DictReader(fh, restkey=EXTRA_FIELDS_KEY, restval=None)
            fieldnames = reader.fieldnames or []
            rows = []
            for i, row in enumerate(reader, start=2):  # header is row 1
                non_extra_values = [v for k, v in row.items() if k != EXTRA_FIELDS_KEY]
                if all(
                    (v is None or str(v).strip() == "") for v in non_extra_values
                ) and not row.get(EXTRA_FIELDS_KEY):
                    continue  # blank trailing line - not a data row

                if EXTRA_FIELDS_KEY in row and row[EXTRA_FIELDS_KEY]:
                    issues.append(
                        ValidationIssue(
                            row_number=i,
                            message=f"Row has more columns than the header "
                            f"(extra values: {row[EXTRA_FIELDS_KEY]!r})",
                        )
                    )
                missing_cols = [k for k, v in row.items() if k != EXTRA_FIELDS_KEY and v is None]
                if missing_cols:
                    issues.append(
                        ValidationIssue(
                            row_number=i,
                            message=f"Row is missing values for column(s): {missing_cols}",
                        )
                    )
                rows.append(row)
        except csv.Error as exc:
            issues.append(ValidationIssue(message=f"CSV could not be parsed: {exc}"))
            return [], [], issues
    return fieldnames, rows, issues


def _is_enabled(value: Optional[str]) -> bool:
    # Matches birthday_sms.csv_reader: blank = enabled; only an explicit
    # falsy value (FALSE/0/NO/N) disables. Kept in sync with that file's
    # `_parse_row` logic since this is only used in the fallback path.
    v = (value or "").strip().upper()
    return v not in {"FALSE", "0", "NO", "N"}


def _fallback_parse_birthday(value: str) -> bool:
    value = (value or "").strip()
    if not value:
        return False
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


# --------------------------------------------------------------------------
# Reuse the project's own parser (primary path)
# --------------------------------------------------------------------------


class _CapturingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.setFormatter(logging.Formatter("%(message)s"))
        self.records: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(self.format(record))


def _reuse_project_parser(path: Path) -> Tuple[bool, List[ValidationIssue], bool, int, int]:
    """Validate via birthday_sms.csv_reader.CsvContactRepository.load().

    Returns (ok, issues, was_used, enabled_count, disabled_count).
    `was_used=False` means the package wasn't importable and the caller
    should rely on the fallback path instead.
    """
    try:
        from birthday_sms.csv_reader import CsvContactRepository  # type: ignore
        from birthday_sms.exceptions import CsvFileNotFoundError, CsvSchemaError  # type: ignore
    except Exception:
        return True, [], False, 0, 0

    handler = _CapturingHandler()
    target_logger = logging.getLogger("birthday_sms.csv_reader")
    prev_level = target_logger.level
    target_logger.addHandler(handler)
    target_logger.setLevel(logging.WARNING)
    try:
        repo = CsvContactRepository(path)
        contacts = repo.load()
    except CsvFileNotFoundError as exc:
        return False, [ValidationIssue(message=str(exc))], True, 0, 0
    except CsvSchemaError as exc:
        return False, [ValidationIssue(message=f"Missing required column(s): {exc}")], True, 0, 0
    finally:
        target_logger.removeHandler(handler)
        target_logger.setLevel(prev_level)

    issues: List[ValidationIssue] = []
    for message in handler.records:
        # Real message looks like: "Skipping CSV row due to error: Row 4: ..."
        # Strip the wrapper prefix; the row number/reason are already inside.
        cleaned = message.removeprefix("Skipping CSV row due to error: ")
        issues.append(ValidationIssue(message=cleaned))

    # Any row the real parser had to skip is treated as a hard validation
    # failure for sync purposes (see module docstring "Reuse policy").
    ok = len(handler.records) == 0

    phones = [c.phone_number for c in contacts]
    duplicates = {p for p in phones if phones.count(p) > 1}
    for phone in sorted(duplicates):
        issues.append(ValidationIssue(message=f"Duplicate PhoneNumber {phone!r}"))
    if duplicates:
        ok = False

    enabled_count = sum(1 for c in contacts if c.enabled)
    disabled_count = len(contacts) - enabled_count

    if enabled_count == 0:
        issues.append(
            ValidationIssue(
                message="No valid, enabled recipient found (need at least one row with "
                "Enabled=TRUE/blank and valid Name, PhoneNumber, and Birthday)"
            )
        )
        ok = False

    return ok, issues, True, enabled_count, disabled_count


# --------------------------------------------------------------------------
# Fallback validator (only runs if birthday_sms isn't importable)
# --------------------------------------------------------------------------


def _fallback_validate_rows(rows: List[Dict[str, str]]) -> Tuple[List[ValidationIssue], int, int]:
    issues: List[ValidationIssue] = []
    seen_phones: Dict[str, int] = {}
    enabled_count = 0
    disabled_count = 0
    valid_enabled_exists = False

    for i, row in enumerate(rows, start=2):
        name = (row.get("Name") or "").strip()
        phone = (row.get("PhoneNumber") or "").strip()
        birthday = (row.get("Birthday") or "").strip()
        enabled_raw = row.get("Enabled")

        if not name:
            issues.append(ValidationIssue(row_number=i, field="Name", message="Name is required"))
        if not phone:
            issues.append(
                ValidationIssue(
                    row_number=i, field="PhoneNumber", message="PhoneNumber is required"
                )
            )
        elif not re.match(r"^\+[1-9]\d{6,14}$", phone):
            issues.append(
                ValidationIssue(
                    row_number=i,
                    field="PhoneNumber",
                    message=f"PhoneNumber {phone!r} is not valid E.164, e.g. +919876543210",
                )
            )

        if not birthday:
            issues.append(
                ValidationIssue(row_number=i, field="Birthday", message="Birthday is required")
            )
        elif not _fallback_parse_birthday(birthday):
            issues.append(
                ValidationIssue(
                    row_number=i,
                    field="Birthday",
                    message=f"Birthday {birthday!r} doesn't match any supported format "
                    f"(YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, MM/DD/YYYY)",
                )
            )

        if phone:
            if phone in seen_phones:
                issues.append(
                    ValidationIssue(
                        row_number=i,
                        field="PhoneNumber",
                        message=f"Duplicate PhoneNumber {phone!r} (also seen at row {seen_phones[phone]})",
                    )
                )
            else:
                seen_phones[phone] = i

        is_enabled = _is_enabled(enabled_raw)
        if is_enabled:
            enabled_count += 1
            if name and phone and birthday and _fallback_parse_birthday(birthday):
                valid_enabled_exists = True
        else:
            disabled_count += 1

    if not valid_enabled_exists:
        issues.append(
            ValidationIssue(
                message="No valid, enabled recipient found (need at least one row with "
                "Enabled=TRUE/blank and valid Name, PhoneNumber, and Birthday)"
            )
        )

    return issues, enabled_count, disabled_count


# --------------------------------------------------------------------------
# Top-level validation
# --------------------------------------------------------------------------


def validate_csv(path: Path) -> ValidationResult:
    if not path.exists():
        return ValidationResult(
            valid=False, issues=[ValidationIssue(message=f"File not found: {path}")]
        )

    if path.stat().st_size == 0:
        return ValidationResult(
            valid=False, issues=[ValidationIssue(message="File is empty (0 bytes)")]
        )

    content = path.read_text(encoding="utf-8-sig").strip()
    if not content:
        return ValidationResult(
            valid=False,
            issues=[ValidationIssue(message="File contains no data after whitespace is stripped")],
        )

    fieldnames, rows, structural_issues = _read_raw(path)
    issues: List[ValidationIssue] = list(structural_issues)

    if not fieldnames:
        issues.append(ValidationIssue(message="Could not read a header row"))
        return ValidationResult(valid=False, issues=issues)

    missing_headers = [h for h in REQUIRED_HEADERS if h not in fieldnames]
    if missing_headers:
        issues.append(
            ValidationIssue(
                message=f"Missing required header(s): {missing_headers}. Found headers: {fieldnames}"
            )
        )
        return ValidationResult(valid=False, issues=issues, fieldnames=fieldnames)

    if not rows:
        issues.append(ValidationIssue(message="CSV has a header row but no data rows"))
        return ValidationResult(valid=False, issues=issues, fieldnames=fieldnames)

    for i, row in enumerate(rows, start=2):
        hint = _sheets_corruption_hint(row.get("PhoneNumber") or "")
        if hint:
            issues.append(ValidationIssue(row_number=i, field="PhoneNumber", message=hint))

    reuse_ok, reuse_issues, reused, enabled_count, disabled_count = _reuse_project_parser(path)
    issues.extend(reuse_issues)

    if not reused:
        fallback_issues, enabled_count, disabled_count = _fallback_validate_rows(rows)
        issues.extend(fallback_issues)
        reuse_ok = len(fallback_issues) == 0

    hard_blockers = [iss for iss in issues if "extra values" not in iss.message]
    is_valid = len(hard_blockers) == 0 and reuse_ok

    return ValidationResult(
        valid=is_valid,
        issues=issues,
        rows=rows,
        fieldnames=fieldnames,
        total=len(rows),
        enabled=enabled_count,
        disabled=disabled_count,
        reused_project_parser=reused,
    )


# --------------------------------------------------------------------------
# Diffing (for the summary + idempotency check)
# --------------------------------------------------------------------------


def _index_by_phone(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    return {
        (r.get("PhoneNumber") or "").strip(): r
        for r in rows
        if (r.get("PhoneNumber") or "").strip()
    }


def diff_rows(
    old_rows: List[Dict[str, str]], new_rows: List[Dict[str, str]]
) -> Tuple[List[str], List[str], List[str]]:
    old_by_phone = _index_by_phone(old_rows)
    new_by_phone = _index_by_phone(new_rows)

    added = sorted(set(new_by_phone) - set(old_by_phone))
    removed = sorted(set(old_by_phone) - set(new_by_phone))
    modified = sorted(
        phone
        for phone in (set(old_by_phone) & set(new_by_phone))
        if {k: v for k, v in old_by_phone[phone].items() if k != EXTRA_FIELDS_KEY}
        != {k: v for k, v in new_by_phone[phone].items() if k != EXTRA_FIELDS_KEY}
    )
    return added, removed, modified


def rows_semantically_equal(old_rows: List[Dict[str, str]], new_rows: List[Dict[str, str]]) -> bool:
    added, removed, modified = diff_rows(old_rows, new_rows)
    return not (added or removed or modified)


# --------------------------------------------------------------------------
# Writing (normalized, so trivial formatting/line-ending diffs from Google
# Sheets exports don't trigger spurious commits)
# --------------------------------------------------------------------------


def write_normalized_csv(fieldnames: List[str], rows: List[Dict[str, str]], target: Path) -> None:
    clean_fieldnames = [f for f in fieldnames if f != EXTRA_FIELDS_KEY]
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=clean_fieldnames, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({k: (row.get(k) or "") for k in clean_fieldnames})
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(buf.getvalue(), encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------
# GitHub Actions integration helpers
# --------------------------------------------------------------------------


def _gha_set_outputs(outputs: Dict[str, object]) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    lines = [f"{k}={v}" for k, v in outputs.items()]
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    else:
        print("\n".join(f"[output] {line}" for line in lines))


def _gha_write_summary(markdown: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown + "\n")
    else:
        print(markdown)


def build_summary_markdown(
    result: ValidationResult,
    changed: bool,
    added: List[str],
    removed: List[str],
    modified: List[str],
    target: Path,
) -> str:
    lines = []
    if result.valid:
        lines.append("## ✅ Google Sheet Sync — Validation Passed")
    else:
        lines.append("## ❌ Google Sheet Sync — Validation Failed")
        lines.append("")
        lines.append(f"`{target}` was **not** modified. The previous version remains in place.")

    lines.append("")
    lines.append(
        f"- Parser used: {'project `CsvContactRepository`' if result.reused_project_parser else 'built-in fallback validator'}"
    )
    lines.append(f"- Total contacts: **{result.total}**")
    lines.append(f"- Enabled: **{result.enabled}**")
    lines.append(f"- Disabled: **{result.disabled}**")

    if result.valid:
        lines.append(f"- Newly added: **{len(added)}**")
        lines.append(f"- Removed: **{len(removed)}**")
        lines.append(f"- Modified: **{len(modified)}**")
        lines.append(
            f"- Repository file changed: **{'yes' if changed else 'no (already up to date)'}**"
        )
        if added:
            lines.append("")
            lines.append("**Added phone numbers:** " + ", ".join(f"`{p}`" for p in added))
        if removed:
            lines.append("")
            lines.append("**Removed phone numbers:** " + ", ".join(f"`{p}`" for p in removed))
        if modified:
            lines.append("")
            lines.append("**Modified phone numbers:** " + ", ".join(f"`{p}`" for p in modified))

    if result.issues:
        lines.append("")
        lines.append(f"### Validation issues ({len(result.issues)})")
        lines.append("")
        for issue in result.issues:
            lines.append(f"- {issue.format()}")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", required=True, type=Path, help="Path to the freshly-downloaded CSV (temp file)"
    )
    parser.add_argument(
        "--target", required=True, type=Path, help="Path to the repository's data/birthdays.csv"
    )
    args = parser.parse_args(argv)

    result = validate_csv(args.source)

    old_rows: List[Dict[str, str]] = []
    if args.target.exists() and args.target.stat().st_size > 0:
        try:
            _, old_rows, _ = _read_raw(args.target)
        except Exception:
            old_rows = []

    added: List[str] = []
    removed: List[str] = []
    modified: List[str] = []
    changed = False

    if result.valid:
        added, removed, modified = diff_rows(old_rows, result.rows)
        changed = not rows_semantically_equal(old_rows, result.rows)
        if changed:
            write_normalized_csv(result.fieldnames, result.rows, args.target)

    summary = build_summary_markdown(result, changed, added, removed, modified, args.target)
    _gha_write_summary(summary)

    _gha_set_outputs(
        {
            "valid": "true" if result.valid else "false",
            "changed": "true" if changed else "false",
            "total": result.total,
            "enabled": result.enabled,
            "disabled": result.disabled,
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
        }
    )

    if not result.valid:
        print("Validation failed:", file=sys.stderr)
        for issue in result.issues:
            print(f"  - {issue.format()}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())