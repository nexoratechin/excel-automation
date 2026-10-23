from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from src.batch import MAX_FILES, process_zip, zip_name_for
from src.config import ConfigError

CLEAN_CSV = b"Name,Email Address,Mobile No\nRahul,rahul@gmail.com,9876543210\n"
DIRTY_CSV = (
    b"Name,Email Address,Mobile No\n"
    b"Rahul,rahul@gmail.com,9876543210\n"
    b"Rahul,RAHUL@GMAIL.COM,9876543210\n"
    b"Karan,karan@gmail,9876543211\n"
)


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def read_zip(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


class TestBatch:
    def test_cleans_every_spreadsheet(self):
        result = process_zip(make_zip({"a.csv": DIRTY_CSV, "b.csv": CLEAN_CSV}))
        assert result.files_ok == 2
        assert result.files_failed == 0
        names = read_zip(result.archive)
        assert "a_cleaned.xlsx" in names
        assert "b_cleaned.xlsx" in names

    def test_totals_are_summed(self):
        result = process_zip(make_zip({"a.csv": DIRTY_CSV, "b.csv": CLEAN_CSV}))
        assert result.kept_total == 1 + 1
        assert result.rejected_total == 2

    def test_summary_csv_is_included(self):
        result = process_zip(make_zip({"a.csv": DIRTY_CSV}))
        summary = read_zip(result.archive)["batch_summary.csv"].decode("utf-8-sig")
        assert "File" in summary
        assert "a.csv" in summary

    def test_per_file_outcomes(self):
        result = process_zip(make_zip({"a.csv": DIRTY_CSV}))
        outcome = result.outcomes[0]
        assert outcome.rows_in == 3
        assert outcome.kept == 1
        assert outcome.rejected == 2
        assert outcome.duplicates == 1
        assert outcome.bad_emails == 1

    def test_ignores_non_spreadsheet_files(self):
        result = process_zip(
            make_zip({"a.csv": CLEAN_CSV, "notes.txt": b"hello", "pic.png": b"x"})
        )
        assert result.files_ok == 1
        assert len(result.outcomes) == 1

    def test_ignores_macos_junk(self):
        result = process_zip(
            make_zip({"a.csv": CLEAN_CSV, "__MACOSX/._a.csv": b"junk"})
        )
        assert result.files_ok == 1

    def test_ignores_hidden_files(self):
        result = process_zip(make_zip({"a.csv": CLEAN_CSV, ".DS_Store": b"junk"}))
        assert result.files_ok == 1

    def test_duplicate_names_across_folders_are_kept_apart(self):
        result = process_zip(
            make_zip({"jan/a.csv": CLEAN_CSV, "feb/a.csv": CLEAN_CSV})
        )
        names = read_zip(result.archive)
        assert "a_cleaned.xlsx" in names
        assert "a_cleaned (2).xlsx" in names

    def test_one_broken_file_does_not_stop_the_batch(self):
        result = process_zip(
            make_zip({"good.csv": CLEAN_CSV, "bad.xlsx": b"not really excel"})
        )
        assert result.files_ok == 1
        assert result.files_failed == 1
        failed = [o for o in result.outcomes if not o.ok]
        assert failed and failed[0].name == "bad.xlsx"
        assert "bad.xlsx" in failed[0].error or "read" in failed[0].error

    def test_xlsx_inside_a_zip_works(self):
        buffer = io.BytesIO()
        pd.DataFrame(
            [("A", "a@gmail.com", "9876543210")],
            columns=["Name", "Email Address", "Mobile No"],
        ).to_excel(buffer, index=False)
        result = process_zip(make_zip({"book.xlsx": buffer.getvalue()}))
        assert result.files_ok == 1
        assert "book_cleaned.xlsx" in read_zip(result.archive)


class TestBatchGuards:
    def test_empty_zip_is_rejected(self):
        with pytest.raises(ConfigError, match="No Excel or CSV"):
            process_zip(make_zip({"notes.txt": b"nothing useful"}))

    def test_not_a_zip_is_rejected(self):
        with pytest.raises(ConfigError, match="damaged or not a real ZIP"):
            process_zip(b"this is a plain text file")

    def test_too_many_files_are_rejected(self):
        files = {f"f{i}.csv": CLEAN_CSV for i in range(MAX_FILES + 1)}
        with pytest.raises(ConfigError, match="limit is 20"):
            process_zip(make_zip(files))

    def test_all_files_unreadable_is_rejected(self):
        with pytest.raises(ConfigError, match="could not be read"):
            process_zip(make_zip({"bad.xlsx": b"garbage"}))

    def test_zip_name_for(self):
        assert zip_name_for("march leads.zip") == "march leads_cleaned.zip"
        assert zip_name_for(".zip") == "batch_cleaned.zip"
