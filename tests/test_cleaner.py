from __future__ import annotations

import pandas as pd
import pytest

from src.cleaner import clean
from src.config import Config, ConfigError


def frame(rows, cols=("Name", "Email Address", "Mobile No")):
    return pd.DataFrame(rows, columns=list(cols))


def config(**kwargs):
    base = dict(
        input_path="in.xlsx",
        output_path="out.xlsx",
        email_col="Email Address",
        phone_col="Mobile No",
        required=["Name"],
    )
    base.update(kwargs)
    return Config(**base)


def test_dedupes_by_email_case_insensitive():
    df = frame([
        ("Rahul", "rahul@gmail.com", "9876543210"),
        ("Rahul S", "RAHUL@GMAIL.COM", "9876543211"),
    ])
    result = clean(df, config())
    assert result.stats.kept == 1
    assert result.stats.duplicates_removed == 1
    assert "same email" in result.rejected.iloc[0]["Reason"]


def test_dedupes_by_phone_when_emails_differ():
    df = frame([
        ("Neha", "neha@gmail.com", "9876543210"),
        ("Neha G", "neha.g@yahoo.com", "+91 98765 43210"),
    ])
    result = clean(df, config())
    assert result.stats.kept == 1
    assert result.stats.duplicates_removed == 1


def test_keeps_rows_with_same_name_but_different_contact():
    df = frame([
        ("Rahul", "rahul1@gmail.com", "9876543210"),
        ("Rahul", "rahul2@gmail.com", "9876543211"),
    ])
    assert clean(df, config()).stats.kept == 2


def test_rejects_invalid_email_and_phone_with_reasons():
    df = frame([
        ("Karan", "karan@gmail", "9876543210"),
        ("Meera", "meera@gmail.com", "12345"),
        ("Good", "good@gmail.com", "9876543211"),
    ])
    result = clean(df, config())
    assert result.stats.kept == 1
    assert result.stats.invalid_email == 1
    assert result.stats.invalid_phone == 1
    reasons = " ".join(result.rejected["Reason"])
    assert "invalid email" in reasons
    assert "invalid phone" in reasons


def test_blank_optional_contact_is_kept():
    df = frame([
        ("Sameer", "", "9876543210"),
        ("Anjali", "anjali@gmail.com", ""),
    ])
    result = clean(df, config())
    assert result.stats.kept == 2
    assert result.stats.blank_email == 1
    assert result.stats.blank_phone == 1


def test_blank_required_field_is_rejected():
    df = frame([("", "someone@gmail.com", "9876543210")])
    result = clean(df, config())
    assert result.stats.kept == 0
    assert "missing required field: Name" in result.rejected.iloc[0]["Reason"]


def test_required_email_rejects_blank():
    df = frame([("Sameer", "", "9876543210")])
    result = clean(df, config(required=["Name", "Email Address"]))
    assert result.stats.kept == 0


def test_blank_rows_are_dropped_silently():
    df = frame([("Rahul", "rahul@gmail.com", "9876543210"), (None, None, None), ("", "", "")])
    result = clean(df, config())
    assert result.stats.blank_rows == 2
    assert result.stats.kept == 1
    assert result.rejected.empty


def test_row_numbers_match_excel():
    df = frame([
        ("Bad", "bad@gmail", "9876543210"),
        ("Good", "good@gmail.com", "9876543211"),
    ])
    result = clean(df, config())
    assert result.rejected.iloc[0]["Row #"] == 2  # header is row 1
    assert result.stats.total_rows == 2


def test_header_offset_shifts_row_numbers():
    df = frame([("Bad", "bad@gmail", "9876543210")])
    result = clean(df, config(header_row=3))
    assert result.rejected.iloc[0]["Row #"] == 4


def test_normalises_values_in_output():
    df = frame([("  rahul ", "  Rahul@Gmail.COM ", "+91 98765 43210")])
    row = clean(df, config()).cleaned.iloc[0]
    assert row["Name"] == "rahul"
    assert row["Email Address"] == "rahul@gmail.com"
    assert row["Mobile No"] == "9876543210"


def test_unknown_column_names_the_available_ones():
    df = frame([("A", "a@gmail.com", "9876543210")])
    with pytest.raises(ConfigError) as exc:
        clean(df, config(email_col="Email"))
    assert "Email Address" in str(exc.value)


def test_column_match_is_forgiving_about_case_and_spacing():
    df = pd.DataFrame([("A", "a@gmail.com", "9876543210")],
                      columns=["Name", "EMAIL ADDRESS", "mobile no"])
    result = clean(df, config(email_col="Email Address", phone_col="Mobile No"))
    assert result.stats.kept == 1


def test_keep_all_on_duplicate():
    df = frame([
        ("Rahul", "rahul@gmail.com", "9876543210"),
        ("Rahul", "rahul@gmail.com", "9876543210"),
    ])
    result = clean(df, config(keep_all_on_duplicate=True))
    assert result.stats.kept == 2
    assert result.stats.duplicates_removed == 1


def test_missing_cells_are_blank_not_the_word_nan():
    # Excel gaps arrive as NaN; str(nan) == "nan" and used to be "validated".
    df = pd.DataFrame([("Sameer", None, "9876543210")],
                      columns=["Name", "Email Address", "Mobile No"])
    result = clean(df, config())
    assert result.stats.kept == 1
    assert result.stats.blank_email == 1
    assert result.stats.invalid_email == 0
    assert result.cleaned.iloc[0]["Email Address"] == ""


def test_empty_dataframe_does_not_crash():
    df = frame([])
    result = clean(df, config())
    assert result.cleaned.empty
    assert result.stats.kept == 0


def test_output_never_overwrites_input():
    cfg = Config(input_path="same.xlsx", output_path="same.xlsx")
    with pytest.raises(ConfigError, match="never modifies"):
        cfg.validate()


def test_unknown_country_rejected():
    with pytest.raises(ConfigError, match="Unknown country"):
        Config(input_path="a.xlsx", output_path="b.xlsx", country="XX").validate()
