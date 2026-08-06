"""
Tests for birthday_sms.validate_and_sync_csv.

Both the real-parser reuse path (birthday_sms.csv_reader.CsvContactRepository)
and the standalone fallback path are exercised deterministically here via
monkeypatching, rather than depending on whatever happens to be importable
in the environment the tests run in.

Run with:
    pytest tests/test_validate_and_sync_csv.py -v
"""

import sys
from pathlib import Path

import pytest

from birthday_sms import validate_and_sync_csv as vsc

VALID_CSV = """Name,PhoneNumber,Birthday,Classification,Brief,Address,Enabled,LastSent,MessageTemplate
Rahul Sharma,+919876543210,1999-05-16,Student,Class 10 - Section B,"12 MG Road, Kolkata",TRUE,,
Priya Das,+919876543211,15/06/2001,Student,Class 9 - Section A,,FALSE,,
"""

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def force_fallback(monkeypatch):
    """Simulate birthday_sms.csv_reader being unimportable, so validate_csv()
    deterministically takes the standalone fallback path regardless of what's
    actually installed in the environment running the tests."""
    monkeypatch.setitem(sys.modules, "birthday_sms.csv_reader", None)
    monkeypatch.setitem(sys.modules, "birthday_sms.exceptions", None)
    yield


# --------------------------------------------------------------------------
# Fallback path (birthday_sms.csv_reader forced unavailable)
# --------------------------------------------------------------------------


def test_valid_csv_passes_fallback(tmp_path, force_fallback):
    src = write(tmp_path, "src.csv", VALID_CSV)
    result = vsc.validate_csv(src)
    assert result.valid, [i.format() for i in result.issues]
    assert result.reused_project_parser is False
    assert result.total == 2
    assert result.enabled == 1
    assert result.disabled == 1


def test_missing_required_header_fails(tmp_path, force_fallback):
    bad = VALID_CSV.replace("PhoneNumber,", "")
    src = write(tmp_path, "src.csv", bad)
    result = vsc.validate_csv(src)
    assert not result.valid
    assert any("Missing required header" in i.message for i in result.issues)


def test_empty_file_fails(tmp_path, force_fallback):
    src = write(tmp_path, "src.csv", "")
    result = vsc.validate_csv(src)
    assert not result.valid
    assert any("empty" in i.message.lower() for i in result.issues)


def test_no_data_rows_fails(tmp_path, force_fallback):
    header_only = "Name,PhoneNumber,Birthday,Classification,Enabled\n"
    src = write(tmp_path, "src.csv", header_only)
    result = vsc.validate_csv(src)
    assert not result.valid
    assert any("no data rows" in i.message for i in result.issues)


def test_duplicate_phone_number_fails_fallback(tmp_path, force_fallback):
    dup = VALID_CSV + "Extra Person,+919876543210,2000-01-01,Student,,,TRUE,,\n"
    src = write(tmp_path, "src.csv", dup)
    result = vsc.validate_csv(src)
    assert not result.valid
    assert any("Duplicate PhoneNumber" in i.message for i in result.issues)


def test_bad_birthday_format_fails_fallback(tmp_path, force_fallback):
    bad = VALID_CSV.replace("1999-05-16", "16-May-1999")
    src = write(tmp_path, "src.csv", bad)
    result = vsc.validate_csv(src)
    assert not result.valid
    assert any("match any supported format" in i.message for i in result.issues)


def test_missing_required_field_fails_fallback(tmp_path, force_fallback):
    bad = VALID_CSV.replace("Rahul Sharma,", ",")
    src = write(tmp_path, "src.csv", bad)
    result = vsc.validate_csv(src)
    assert not result.valid
    assert any("Name" in i.message and "required" in i.message for i in result.issues)


def test_no_enabled_recipient_fails_fallback(tmp_path, force_fallback):
    all_disabled = VALID_CSV.replace(",TRUE,,", ",FALSE,,")
    src = write(tmp_path, "src.csv", all_disabled)
    result = vsc.validate_csv(src)
    assert not result.valid
    assert any("No valid, enabled recipient" in i.message for i in result.issues)


def test_malformed_row_extra_or_missing_columns_flagged(tmp_path, force_fallback):
    # Second data row has one field too few - this check is file-structural
    # and runs identically regardless of which parser handles row content.
    bad = VALID_CSV + "Short Row,+919876543299,2000-01-01,Student\n"
    src = write(tmp_path, "src.csv", bad)
    result = vsc.validate_csv(src)
    assert not result.valid
    assert any("missing values for column" in i.message for i in result.issues)


def test_full_sync_flow_no_op_when_unchanged(tmp_path, force_fallback):
    src = write(tmp_path, "src.csv", VALID_CSV)
    target = tmp_path / "data" / "birthdays.csv"

    rc1 = vsc.main(["--source", str(src), "--target", str(target)])
    assert rc1 == 0
    assert target.exists()
    first_content = target.read_text(encoding="utf-8")

    # Re-run sync with the exact same source content; nothing should change
    # even though it's a fresh temp file (different mtime/inode).
    src2 = write(tmp_path, "src2.csv", VALID_CSV)
    rc2 = vsc.main(["--source", str(src2), "--target", str(target)])
    assert rc2 == 0
    assert target.read_text(encoding="utf-8") == first_content


def test_full_sync_flow_rejects_invalid_and_preserves_existing(tmp_path, force_fallback):
    src_good = write(tmp_path, "good.csv", VALID_CSV)
    target = tmp_path / "data" / "birthdays.csv"
    assert vsc.main(["--source", str(src_good), "--target", str(target)]) == 0
    preserved = target.read_text(encoding="utf-8")

    bad_csv = VALID_CSV.replace("1999-05-16", "not-a-date")
    src_bad = write(tmp_path, "bad.csv", bad_csv)
    rc = vsc.main(["--source", str(src_bad), "--target", str(target)])
    assert rc == 1
    assert target.read_text(encoding="utf-8") == preserved


# --------------------------------------------------------------------------
# Diffing / idempotency (parser-independent, no fixture needed)
# --------------------------------------------------------------------------


def test_diff_added_removed_modified():
    old_rows = [
        {"Name": "A", "PhoneNumber": "+911", "Birthday": "2000-01-01", "Enabled": "TRUE"},
        {"Name": "B", "PhoneNumber": "+912", "Birthday": "2000-01-02", "Enabled": "TRUE"},
    ]
    new_rows = [
        {
            "Name": "A",
            "PhoneNumber": "+911",
            "Birthday": "2000-01-01",
            "Enabled": "FALSE",
        },  # modified
        {"Name": "C", "PhoneNumber": "+913", "Birthday": "2000-01-03", "Enabled": "TRUE"},  # added
        # B removed
    ]
    added, removed, modified = vsc.diff_rows(old_rows, new_rows)
    assert added == ["+913"]
    assert removed == ["+912"]
    assert modified == ["+911"]


def test_idempotent_when_semantically_identical():
    rows_a = [{"Name": "A", "PhoneNumber": "+911", "Birthday": "2000-01-01", "Enabled": "TRUE"}]
    rows_b = [{"Name": "A", "PhoneNumber": "+911", "Birthday": "2000-01-01", "Enabled": "TRUE"}]
    assert vsc.rows_semantically_equal(rows_a, rows_b)


# --------------------------------------------------------------------------
# Reuse path (real birthday_sms.csv_reader.CsvContactRepository, no
# monkeypatching - this is what actually runs in CI once `pip install -e .`
# has made the package importable)
# --------------------------------------------------------------------------


def test_valid_csv_passes_reuse():
    src = FIXTURES / "sample_birthdays.csv"
    result = vsc.validate_csv(src)
    assert result.reused_project_parser is True
    assert result.valid, [i.format() for i in result.issues]
    assert result.total == 44
    assert result.enabled == 44
    assert result.disabled == 0


def test_reuse_path_surfaces_real_parser_error_messages(tmp_path):
    csv_content = (
        "Name,PhoneNumber,Birthday,Classification,Brief,Address,Enabled,LastSent,MessageTemplate\n"
        "Good Person,+919876543210,1999-05-16,Student,,,TRUE,,\n"
        ",+919876543299,2000-01-01,Student,,,TRUE,,\n"  # missing name
        "Bad Date Person,+919876543211,16-May-1999,Student,,,TRUE,,\n"  # bad date
        "Bad Phone Person,12345,2000-01-01,Student,,,TRUE,,\n"  # bad phone
    )
    src = tmp_path / "src.csv"
    src.write_text(csv_content, encoding="utf-8")

    result = vsc.validate_csv(src)

    assert result.reused_project_parser is True
    assert not result.valid
    messages = " | ".join(i.message for i in result.issues)
    assert "Name is required but was empty" in messages
    # Real message from birthday_sms.date_utils is "Could not parse
    # birthday '...'. Supported formats: ...". Match on wording that
    # won't break if the exact phrasing shifts slightly.
    assert "16-May-1999" in messages and "upported format" in messages
    assert "is not valid E.164" in messages


def test_reuse_path_catches_duplicate_after_real_parsing(tmp_path):
    csv_content = (
        "Name,PhoneNumber,Birthday,Classification,Brief,Address,Enabled,LastSent,MessageTemplate\n"
        "Person A,+919876543210,1999-05-16,Student,,,TRUE,,\n"
        "Person B,+919876543210,2000-06-01,Student,,,TRUE,,\n"
    )
    src = tmp_path / "src.csv"
    src.write_text(csv_content, encoding="utf-8")

    result = vsc.validate_csv(src)

    assert result.reused_project_parser is True
    assert not result.valid
    assert any("Duplicate PhoneNumber" in i.message for i in result.issues)


def test_reuse_path_full_sync_end_to_end_with_real_sample(tmp_path):
    target = tmp_path / "data" / "birthdays.csv"
    rc = vsc.main(["--source", str(FIXTURES / "sample_birthdays.csv"), "--target", str(target)])
    assert rc == 0
    assert target.exists()
    # 44 contacts + header line
    assert len(target.read_text(encoding="utf-8").strip().splitlines()) == 45


# --------------------------------------------------------------------------
# Google Sheets auto-formatting corruption detection (scientific notation /
# stripped '+' from an un-Plain-Text-formatted PhoneNumber column)
# --------------------------------------------------------------------------


def test_detects_scientific_notation_phone_number(tmp_path):
    csv_content = (
        "Name,PhoneNumber,Birthday,Classification,Brief,Address,Enabled,LastSent,MessageTemplate\n"
        "Corrupted Person,9.19878E+11,1999-05-16,Student,,,TRUE,,\n"
    )
    src = tmp_path / "src.csv"
    src.write_text(csv_content, encoding="utf-8")

    result = vsc.validate_csv(src)

    assert not result.valid
    assert any(
        "auto-converted it to a number (scientific notation)" in i.message for i in result.issues
    ), [i.format() for i in result.issues]
    assert any("Plain text" in i.message for i in result.issues)


def test_detects_stripped_plus_prefix_phone_number(tmp_path):
    csv_content = (
        "Name,PhoneNumber,Birthday,Classification,Brief,Address,Enabled,LastSent,MessageTemplate\n"
        "Corrupted Person,919876543211,2000-06-01,Student,,,TRUE,,\n"
    )
    src = tmp_path / "src.csv"
    src.write_text(csv_content, encoding="utf-8")

    result = vsc.validate_csv(src)

    assert not result.valid
    assert any(
        "stripped it by treating the cell as a number" in i.message for i in result.issues
    ), [i.format() for i in result.issues]


def test_normal_e164_phone_number_not_flagged_as_corrupted(tmp_path):
    csv_content = (
        "Name,PhoneNumber,Birthday,Classification,Brief,Address,Enabled,LastSent,MessageTemplate\n"
        "Normal Person,+919876543212,2001-01-01,Student,,,TRUE,,\n"
    )
    src = tmp_path / "src.csv"
    src.write_text(csv_content, encoding="utf-8")

    result = vsc.validate_csv(src)

    assert result.valid, [i.format() for i in result.issues]
    assert not any("Google Sheets" in i.message for i in result.issues)