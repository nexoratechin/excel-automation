from __future__ import annotations

import pytest

from src.validators import clean_text, normalize_email, normalize_phone


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


class TestCleanText:
    def test_nbsp_and_padding(self):
        assert clean_text("  Rahul\u00a0  Sharma  ") == "Rahul Sharma"

    def test_zero_width(self):
        assert clean_text("Rahul\u200bSharma") == "RahulSharma"

    def test_none(self):
        assert clean_text(None) == ""
