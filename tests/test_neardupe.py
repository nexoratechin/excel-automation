from __future__ import annotations

import pandas as pd

from src.neardupe import find_possible_duplicates, name_score, normalize_name


class TestNormalizeName:
    def test_lowercase_and_punctuation(self):
        assert normalize_name("  Rahul   Sharma. ") == "rahul sharma"

    def test_drops_honorifics(self):
        assert normalize_name("Mr. Rahul Sharma") == "rahul sharma"
        assert normalize_name("Dr Priya Patel") == "priya patel"

    def test_keeps_initials(self):
        assert normalize_name("Rahul S.") == "rahul s"


class TestNameScore:
    def test_identical(self):
        score, reason = name_score("rahul sharma", "rahul sharma")
        assert score == 1.0 and reason

    def test_initial_matches_full_name(self):
        score, reason = name_score("rahul s", "rahul sharma")
        assert score >= 0.9
        assert "initial" in reason or "part of" in reason

    def test_missing_surname_is_flagged(self):
        score, reason = name_score("rahul", "rahul sharma")
        assert score >= 0.9
        assert reason

    def test_different_people_are_not_flagged(self):
        score, reason = name_score("rahul sharma", "rohit sharma")
        assert reason == ""

    def test_different_people_with_same_surname(self):
        assert name_score("priya patel", "meera patel")[1] == ""


class TestFindPossibleDuplicates:
    def frame(self, rows):
        return find_possible_duplicates(
            rows=[r[0] for r in rows],
            names=[r[1] for r in rows],
            emails=[r[2] for r in rows],
            phones=[r[3] for r in rows],
        )

    def test_flags_initial_form_of_the_same_person(self):
        result = self.frame([
            (2, "Rahul Sharma", "rahul1@gmail.com", "9876543210"),
            (7, "Rahul S.", "rahul2@gmail.com", "9876543211"),
        ])
        assert len(result) == 1
        assert result.iloc[0]["Row A"] == 2
        assert result.iloc[0]["Row B"] == 7
        assert result.iloc[0]["Score"] >= 90

    def test_does_not_flag_different_people(self):
        result = self.frame([
            (2, "Rahul Sharma", "rahul@gmail.com", "9876543210"),
            (3, "Rohit Sharma", "rohit@gmail.com", "9876543211"),
        ])
        assert result.empty

    def test_skips_pairs_already_identical(self):
        # Same email or phone means exact de-duplication already handled it.
        result = self.frame([
            (2, "Rahul Sharma", "same@gmail.com", "9876543210"),
            (3, "Rahul Sharma", "same@gmail.com", "9876543211"),
        ])
        assert result.empty

    def test_ignores_rows_without_a_name(self):
        result = self.frame([
            (2, "", "a@gmail.com", "9876543210"),
            (3, "", "b@gmail.com", "9876543211"),
        ])
        assert result.empty

    def test_columns_are_stable_even_when_empty(self):
        result = self.frame([(2, "A B", "", "")])
        assert list(result.columns) == [
            "Row A", "Row B", "Name A", "Name B",
            "Email A", "Email B", "Phone A", "Phone B", "Score", "Why",
        ]


class TestCleanerIntegration:
    def test_review_sheet_appears_without_changing_the_rows(self):
        from src.cleaner import clean
        from src.config import Config

        df = pd.DataFrame(
            [
                ("Rahul Sharma", "rahul1@gmail.com", "9876543210"),
                ("Rahul S.", "rahul2@gmail.com", "9876543211"),
            ],
            columns=["Name", "Email Address", "Mobile No"],
        )
        cfg = Config(
            input_path="x.xlsx", output_path="y.xlsx",
            email_col="Email Address", phone_col="Mobile No", name_col="Name",
        )
        result = clean(df, cfg)
        assert result.stats.kept == 2            # nothing removed
        assert result.stats.possible_duplicates == 1
        assert len(result.possible) == 1

    def test_disabled_by_config(self):
        from src.cleaner import clean
        from src.config import Config

        df = pd.DataFrame(
            [("Rahul Sharma", "a@gmail.com", "9876543210"),
             ("Rahul S.", "b@gmail.com", "9876543211")],
            columns=["Name", "Email Address", "Mobile No"],
        )
        cfg = Config(
            input_path="x.xlsx", output_path="y.xlsx",
            email_col="Email Address", phone_col="Mobile No", name_col="Name",
            review_near_duplicates=False,
        )
        result = clean(df, cfg)
        assert result.stats.possible_duplicates == 0
        assert result.possible.empty
