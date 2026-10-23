from __future__ import annotations

import pandas as pd
import pytest

from src.config import ConfigError
from src.reader import guess_business_columns, guess_columns, read_table, resolve_column


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


def test_csv_with_a_stray_quote_still_reads(tmp_path):
    # '"Rahul" Sharma' makes pandas' Python engine fail with
    # "',' expected after '"'". The C engine copes, so the file must load.
    src = tmp_path / "quoted.csv"
    src.write_text('Name,Email Address\n"Rahul" Sharma,rahul@gmail.com\n', encoding="utf-8")
    df = read_table(src)
    assert len(df) == 1
    assert "Sharma" in df.iloc[0]["Name"]


def test_unrecoverable_csv_raises_a_readable_error(tmp_path):
    # An unterminated quote breaks both engines.
    src = tmp_path / "broken.csv"
    src.write_text('Name,Email\nRahul,"rahul@gmail.com\n', encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        read_table(src)
    message = str(exc.value)
    assert "CSV file could not be read" in message
    assert "Save As" in message
    assert "ParserError" not in message
    assert "input.csv" not in message


def test_read_table_rejects_unknown_extension(tmp_path):
    src = tmp_path / "notes.docx"
    src.write_text("hello", encoding="utf-8")
    with pytest.raises(ConfigError, match="Unsupported file type"):
        read_table(src)


class TestBusinessColumnDetection:
    def test_detects_gstin_by_header_and_content(self):
        df = pd.DataFrame({"GSTIN": ["27AAPFU0939F1ZV", "29AAGCB7383J1Z8", "07AAACC1206D1ZI"]})
        gstin, _pan, _pin = guess_business_columns(df)
        assert gstin == "GSTIN"

    def test_does_not_mistake_six_digit_ids_for_pincodes(self):
        # "Order ID" must not be validated as a pincode: half of these would be
        # rejected for a leading zero.
        df = pd.DataFrame({"Order ID": ["012345", "098765", "043210", "011111"]})
        _g, _p, pin = guess_business_columns(df)
        assert pin is None

    def test_does_not_treat_a_company_column_as_pan(self):
        df = pd.DataFrame({"Company": ["Acme Pvt Ltd", "Beta Traders", "Gamma LLP"]})
        _g, pan, _pin = guess_business_columns(df)
        assert pan is None

    def test_content_must_agree_with_the_header(self):
        # A GSTIN header with rubbish values must not be selected.
        df = pd.DataFrame({"GSTIN": ["n/a", "unknown", "pending", "none"]})
        gstin, _p, _pin = guess_business_columns(df)
        assert gstin is None

    def test_detects_pincode(self):
        df = pd.DataFrame({"Pincode": ["400001", "110001", "560001", "600001"]})
        _g, _p, pin = guess_business_columns(df)
        assert pin == "Pincode"
