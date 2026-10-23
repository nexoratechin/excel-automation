from __future__ import annotations

import pytest

from src.validators import (
    clean_text,
    normalize_email,
    normalize_gstin,
    normalize_pan,
    normalize_phone,
    normalize_pincode,
)


class TestEmail:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("rahul.sharma@gmail.com", "rahul.sharma@gmail.com"),
            ("  Priya.Patel@Yahoo.COM  ", "priya.patel@yahoo.com"),
            ("john+tag@sub.example.co.in", "john+tag@sub.example.co.in"),
            ("MAILTO:Ravi@Rediffmail.com", "ravi@rediffmail.com"),
            ("sneha\u00a0iyer@gmail.com", "snehaiyer@gmail.com"),
        ],
    )
    def test_valid(self, raw, expected):
        value, error = normalize_email(raw)
        assert error is None
        assert value == expected

    @pytest.mark.parametrize(
        "raw",
        ["karan.mehta@gmail", "divya@@gmail.com", "arjun.rao@", "@gmail.com",
         "john doe@gmail.com", "john..doe@gmail.com", ".john@gmail.com", "no-at-sign.com"],
    )
    def test_invalid(self, raw):
        value, error = normalize_email(raw)
        assert value is None
        assert error == "invalid email"

    def test_empty(self):
        assert normalize_email("   ") == (None, "empty")
        assert normalize_email(None) == (None, "empty")


class TestPhone:
    @pytest.mark.parametrize(
        "raw",
        ["9876543210", "+91 98765 43210", "+919876543210", "09876543210",
         "919876543210", "98765-43210", "9876543210", "98765\u00a043210"],
    )
    def test_indian_variants_normalise_to_same(self, raw):
        value, error = normalize_phone(raw, "IN", "local")
        assert error is None
        assert value == "9876543210"

    @pytest.mark.parametrize(
        "raw",
        ["12345", "98765abcde", "1234567890", "5876543210", "1234567890123", "abcdef", "0"],
    )
    def test_invalid_indian(self, raw):
        value, error = normalize_phone(raw, "IN", "local")
        assert value is None
        assert error == "invalid phone"

    def test_e164(self):
        assert normalize_phone("9876543210", "IN", "e164") == ("+919876543210", None)

    def test_digits(self):
        assert normalize_phone("+91 98765 43210", "IN", "digits") == ("9876543210", None)

    def test_us(self):
        assert normalize_phone("(415) 555-2671", "US", "local") == ("4155552671", None)
        assert normalize_phone("+1 415 555 2671", "US", "e164") == ("+14155552671", None)

    def test_any(self):
        assert normalize_phone("+44 7700 900123", "ANY", "digits") == ("447700900123", None)

    def test_empty(self):
        assert normalize_phone("") == (None, "empty")


class TestNumericPhones:
    """Excel stores every number as a float; a phone column always arrives as
    9876543210.0. Stripping digits from that used to yield 98765432100 and then
    keep the last ten, silently producing a different number."""

    @pytest.mark.parametrize(
        "raw", ["9876543210.0", "9876543210.000", "9876543210.", 9876543210.0, 9876543210]
    )
    def test_numeric_values_keep_the_real_number(self, raw):
        assert normalize_phone(raw, "IN", "local") == ("9876543210", None)

    def test_numeric_with_country_prefix(self):
        assert normalize_phone("+91 98765 43210.0", "IN", "local") == ("9876543210", None)

    def test_fractional_part_is_rejected_not_truncated(self):
        assert normalize_phone("9876543210.5") == (None, "invalid phone")

    def test_scientific_notation_text_is_rejected(self):
        # The string "9.87654E+09" has already lost digits upstream.
        assert normalize_phone("9.87654E+09") == (None, "invalid phone")

    def test_float_value_is_taken_at_face_value(self):
        # 9.87654e9 really is 9876540000.0; there is nothing to recover.
        assert normalize_phone(9.87654e9, "IN", "local") == ("9876540000", None)

    def test_extension_text_is_rejected(self):
        assert normalize_phone("9876543210 ext 12") == (None, "invalid phone")


class TestCleanText:
    def test_nbsp_and_padding(self):
        assert clean_text("  Rahul\u00a0  Sharma  ") == "Rahul Sharma"

    def test_zero_width(self):
        assert clean_text("Rahul\u200bSharma") == "RahulSharma"

    def test_none(self):
        assert clean_text(None) == ""


class TestGstin:
    def test_valid(self):
        assert normalize_gstin("27AAPFU0939F1ZV") == ("27AAPFU0939F1ZV", None)

    def test_lowercase_and_spaces_are_normalised(self):
        assert normalize_gstin(" 27aapfu0939f1zv ") == ("27AAPFU0939F1ZV", None)

    @pytest.mark.parametrize(
        "raw",
        [
            "27AAPFU0939F1Z",      # too short
            "27AAPFU0939F1ZVX",    # too long
            "00AAPFU0939F1ZV",     # no such state code
            "27AAPFU0939F1",       # truncated
            "27AAPF00939F1ZV",     # digits in the PAN block
            "A7AAPFU0939F1ZV",     # first two must be digits
        ],
    )
    def test_invalid(self, raw):
        assert normalize_gstin(raw) == (None, "invalid GSTIN")

    def test_empty(self):
        assert normalize_gstin("") == (None, "empty")
        assert normalize_gstin(None) == (None, "empty")


class TestPan:
    def test_valid(self):
        assert normalize_pan("AAPFU0939F") == ("AAPFU0939F", None)

    def test_lowercase_is_normalised(self):
        assert normalize_pan(" aapfu0939f ") == ("AAPFU0939F", None)

    @pytest.mark.parametrize("raw", ["AAPFU0939", "AAPF0939F", "AAPFU09391", "1234567890"])
    def test_invalid(self, raw):
        assert normalize_pan(raw) == (None, "invalid PAN")


class TestPincode:
    @pytest.mark.parametrize("raw", ["400001", "400 001", 400001, 400001.0, "400001.0"])
    def test_valid(self, raw):
        assert normalize_pincode(raw) == ("400001", None)

    @pytest.mark.parametrize("raw", ["040001", "40001", "4000012", "abcde1", 400001.5])
    def test_invalid(self, raw):
        assert normalize_pincode(raw) == (None, "invalid pincode")
