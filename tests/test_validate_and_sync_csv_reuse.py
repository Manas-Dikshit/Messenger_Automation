"""
Tests that exercise the *reuse* code path in
scripts/validate_and_sync_csv.py - i.e. the branch that actually calls
birthday_sms.csv_reader.CsvContactRepository.load(), rather than the
standalone fallback validator.

These run automatically as part of the normal `pytest` invocation inside
the real repository, where `birthday_sms` is already importable (it's
installed via `pip install -e .` same as every other test module here).
If `birthday_sms` is *not* importable in whatever environment runs this
file (e.g. copied out of the repo in isolation), these tests are skipped
rather than failing, since scripts/validate_and_sync_csv.py's own fallback
path is what covers that scenario instead (see
test_validate_and_sync_csv.py).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_and_sync_csv as vsc  # noqa: E402

birthday_sms = pytest.importorskip(
    "birthday_sms.csv_reader",
    reason="birthday_sms not importable in this environment; "
    "the fallback validator path is covered separately.",
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_real_sample_data_is_valid_via_reuse_path():
    result = vsc.validate_csv(FIXTURES / "sample_birthdays.csv")
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
    assert "does not match any supported format" in messages
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
