from __future__ import annotations

import pandas as pd
import pytest

from src.config import ConfigError
from src.reader import guess_columns, read_table, resolve_column


def test_guess_uses_content_not_header_names():
    df = pd.DataFrame(
        {
            "Field 1": ["a@gmail.com", "b@yahoo.com", "c@outlook.com"],
            "Field 2": ["9876543210", "9876543211", "9876543212"],
            "City": ["Mumbai", "Delhi", "Pune"],
        }
    )
    email_col, phone_col = guess_columns(df)
    assert email_col == "Field 1"
    assert phone_col == "Field 2"


def test_guess_ignores_name_column_that_looks_like_a_phone_header():
    df = pd.DataFrame(
        {
            "Contact Person": ["Rahul Sharma", "Priya Patel", "Amit Verma"],
            "Number": ["9876543210", "9876543211", "9876543212"],
        }
    )
    email_col, phone_col = guess_columns(df)
    assert email_col is None
    assert phone_col == "Number"


def test_guess_returns_none_when_nothing_validates():
    df = pd.DataFrame({"Notes": ["call back", "no answer", "busy"]})
    assert guess_columns(df) == (None, None)


def test_guess_falls_back_to_header_keyword_when_data_is_dirty():
    df = pd.DataFrame({"Email": ["broken1", "broken2", "broken3", "ok@gmail.com"]})
    email_col, _ = guess_columns(df)
    assert email_col == "Email"


def test_guess_ignores_short_columns():
    df = pd.DataFrame({"Maybe": ["a@gmail.com"], "Other": ["x"]})
    assert guess_columns(df)[0] is None


def test_resolve_column_exact():
    df = pd.DataFrame(columns=["Email Address"])
    assert resolve_column(df, "Email Address", "email") == "Email Address"


def test_resolve_column_case_and_spacing():
    df = pd.DataFrame(columns=["  EMAIL   ADDRESS "])
    assert resolve_column(df, "Email Address", "email") == "  EMAIL   ADDRESS "


def test_resolve_column_missing_lists_options():
    df = pd.DataFrame(columns=["Name", "Mobile No"])
    with pytest.raises(ConfigError) as exc:
        resolve_column(df, "Email", "email")
    assert "Mobile No" in str(exc.value)


def test_read_table_keeps_phone_as_text(tmp_path):
    src = tmp_path / "numbers.xlsx"
    pd.DataFrame({"Mobile": [9876543210, 9123456780]}).to_excel(src, index=False)
    df = read_table(src)
    assert df["Mobile"].tolist() == ["9876543210", "9123456780"]


def test_read_table_semicolon_csv(tmp_path):
    src = tmp_path / "semi.csv"
    src.write_text("Name;Email\nRahul;rahul@gmail.com\n", encoding="utf-8")
    df = read_table(src)
    assert list(df.columns) == ["Name", "Email"]
    assert df.iloc[0]["Email"] == "rahul@gmail.com"


def test_read_table_rejects_unknown_extension(tmp_path):
    src = tmp_path / "notes.docx"
    src.write_text("hello", encoding="utf-8")
    with pytest.raises(ConfigError, match="Unsupported file type"):
        read_table(src)
