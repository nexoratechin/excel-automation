from __future__ import annotations

import pytest

from src.request_parser import describe, parse_request


class TestDuplicates:
    def test_keep_duplicates(self):
        plan = parse_request("please keep the duplicates, I want to see them")
        assert plan.keep_duplicates is True
        assert plan.applied

    def test_dont_remove_duplicates_means_keep(self):
        plan = parse_request("don't remove duplicates")
        assert plan.keep_duplicates is True

    def test_remove_duplicates(self):
        plan = parse_request("remove duplicate contacts")
        assert plan.keep_duplicates is False

    def test_no_opinion_leaves_it_alone(self):
        assert parse_request("my emails have spaces").keep_duplicates is None


class TestPhone:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("write numbers with +91", "e164"),
            ("international format please", "e164"),
            ("digits only", "digits"),
            ("10 digit numbers", "local"),
            ("local format", "local"),
        ],
    )
    def test_phone_format(self, text, expected):
        assert parse_request(text).phone_format == expected

    def test_country(self):
        assert parse_request("these are US numbers").country == "US"
        assert parse_request("indian numbers").country == "IN"
        assert parse_request("numbers from any country").country == "ANY"

    def test_skip_phone(self):
        plan = parse_request("ignore the phone column, it is fine")
        assert plan.skip_phone is True


class TestEmailAndHeaders:
    def test_skip_email(self):
        plan = parse_request("don't check emails")
        assert plan.skip_email is True

    def test_header_row_number(self):
        assert parse_request("my headers are on row 3").header_row == 3
        assert parse_request("row 5 has the header").header_row == 5

    def test_title_row_means_row_two(self):
        assert parse_request("there is a title row above the headers").header_row == 2

    def test_absurd_header_row_is_ignored(self):
        assert parse_request("headers are on row 999").header_row is None


class TestUnsupported:
    def test_email_verification_is_called_out(self):
        plan = parse_request("verify that the emails really exist")
        assert plan.unsupported
        assert "format" in plan.unsupported[0]
        # It must not silently switch email checking off.
        assert plan.skip_email is False

    def test_merging_is_called_out(self):
        plan = parse_request("merge the duplicate rows together")
        assert plan.unsupported

    def test_crm_is_called_out(self):
        plan = parse_request("push this into salesforce")
        assert plan.unsupported

    def test_normal_request_has_no_warnings(self):
        assert parse_request("keep duplicates and use +91").unsupported == []


class TestCombined:
    def test_realistic_sentence(self):
        plan = parse_request(
            "My phone numbers should have +91 and my header is on row 2. "
            "Also don't remove duplicates."
        )
        assert plan.phone_format == "e164"
        assert plan.header_row == 2
        assert plan.keep_duplicates is True
        assert len(plan.applied) == 3

    def test_empty_request_does_nothing(self):
        plan = parse_request("   ")
        assert plan.touched is False
        assert describe(plan) == ""

    def test_gstin_mention_is_confirmed_back(self):
        plan = parse_request("also validate the gstin column")
        assert plan.applied
        assert "GSTIN" in describe(plan)

    def test_gst_portal_request_is_not_confirmed(self):
        plan = parse_request("verify the gstin on the government portal")
        assert plan.unsupported
        assert not any("will be checked" in line for line in plan.applied)

    def test_describe_reads_like_english(self):
        text = describe(parse_request("keep duplicates"))
        assert "kept" in text
