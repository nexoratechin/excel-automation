"""Normalise, validate and de-duplicate a contact table.

Rules, in the order they are applied to each row:

1. Fully empty rows are dropped silently (they are formatting noise).
2. Values are trimmed of whitespace / invisible characters.
3. Emails and phones are normalised, then validated. A blank value is only a
   rejection if that column was listed in ``required``.
4. A row is rejected if it breaks any rule; the reason is recorded.
5. Remaining rows are de-duplicated on normalised email, else phone, else the
   whole row. The first occurrence wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .config import Config
from .reader import resolve_column
from .validators import clean_text, normalize_email, normalize_phone

REASON_DUPLICATE = "duplicate"


@dataclass
class Stats:
    total_rows: int = 0
    kept: int = 0
    rejected: int = 0
    duplicates_removed: int = 0
    invalid_email: int = 0
    invalid_phone: int = 0
    missing_required: int = 0
    blank_email: int = 0
    blank_phone: int = 0
    blank_rows: int = 0
    reason_counts: dict[str, int] = field(default_factory=dict)

    def note(self, reason: str) -> None:
        head = reason.split(":")[0].split(" (")[0].strip()
        self.reason_counts[head] = self.reason_counts.get(head, 0) + 1


@dataclass
class CleanResult:
    cleaned: pd.DataFrame
    rejected: pd.DataFrame
    stats: Stats
    mapping: dict[str, str]
    duplicates_examples: list[str] = field(default_factory=list)


def clean(df: pd.DataFrame, cfg: Config) -> CleanResult:
    if df.empty:
        empty = pd.DataFrame(columns=["Row #", "Reason", *df.columns])
        return CleanResult(df.copy(), empty, Stats(), {})

    mapping: dict[str, str] = {}
    if cfg.email_col:
        mapping["email"] = resolve_column(df, cfg.email_col, "email")
    if cfg.phone_col:
        mapping["phone"] = resolve_column(df, cfg.phone_col, "phone")
    if cfg.name_col:
        mapping["name"] = resolve_column(df, cfg.name_col, "name")
    for col in cfg.required:
        if col in df.columns:
            continue
        resolved = resolve_column(df, col, "required field")
        cfg.required = [resolved if c == col else c for c in cfg.required]

    columns = [str(c) for c in df.columns]
    position = {col: i for i, col in enumerate(columns)}
    email_pos = position.get(mapping.get("email", ""))
    phone_pos = position.get(mapping.get("phone", ""))
    required_pos = {c: position[c] for c in cfg.required if c in position}
    missing_required = [c for c in cfg.required if c not in position]
    if missing_required:
        # resolve_column above raises for unknown columns, so this is defensive.
        raise ValueError(f"Required columns missing after resolution: {missing_required}")

    stats = Stats(total_rows=len(df))
    kept_rows: list[dict] = []
    rejected_rows: list[dict] = []
    seen_email: dict[str, int] = {}
    seen_phone: dict[str, int] = {}
    seen_row: dict[tuple, int] = {}
    duplicate_examples: list[str] = []

    for offset, values in enumerate(df.itertuples(index=False, name=None)):
        row_no = cfg.header_row + 1 + offset
        raw = {col: values[i] for i, col in enumerate(columns)}
        if all(not clean_text(v) for v in values):
            stats.blank_rows += 1
            continue

        record = {col: clean_text(v) for col, v in raw.items()}
        problems: list[str] = []

        if email_pos is not None and "email" in mapping:
            email, error = normalize_email(values[email_pos])
            if error == "empty":
                stats.blank_email += 1
                record[mapping["email"]] = ""
                if mapping["email"] in required_pos:
                    problems.append(f"missing required field: {mapping['email']}")
            elif error:
                stats.invalid_email += 1
                problems.append(f"invalid email: {record[mapping['email']]!r}")
            else:
                record[mapping["email"]] = email or ""

        if phone_pos is not None and "phone" in mapping:
            phone, error = normalize_phone(values[phone_pos], cfg.country, cfg.phone_format)
            if error == "empty":
                stats.blank_phone += 1
                record[mapping["phone"]] = ""
                if mapping["phone"] in required_pos:
                    problems.append(f"missing required field: {mapping['phone']}")
            elif error:
                stats.invalid_phone += 1
                problems.append(f"invalid phone: {record[mapping['phone']]!r}")
            else:
                record[mapping["phone"]] = phone or ""

        for col in cfg.required:
            if col in (mapping.get("email"), mapping.get("phone")):
                continue
            if not record.get(col, "").strip():
                problems.append(f"missing required field: {col}")

        if problems:
            stats.missing_required += sum(1 for p in problems if p.startswith("missing required"))
            for problem in problems:
                stats.note(problem)
            stats.rejected += 1
            rejected_rows.append({"Row #": row_no, "Reason": " | ".join(problems), **record})
            continue

        email_value = record.get(mapping.get("email", ""), "").strip().lower()
        phone_value = record.get(mapping.get("phone", ""), "").strip()
        row_key = tuple(v.strip().lower() for v in record.values())

        duplicate_of: int | None = None
        duplicate_why = ""
        if email_value and email_value in seen_email:
            duplicate_of = seen_email[email_value]
            duplicate_why = f"same email {email_value}"
        elif phone_value and phone_value in seen_phone:
            duplicate_of = seen_phone[phone_value]
            duplicate_why = f"same phone {phone_value}"
        elif not email_value and not phone_value and row_key in seen_row:
            duplicate_of = seen_row[row_key]
            duplicate_why = "identical row"

        if duplicate_of is not None:
            stats.duplicates_removed += 1
            stats.note(REASON_DUPLICATE)
            if len(duplicate_examples) < 5:
                duplicate_examples.append(f"row {row_no} duplicate of row {duplicate_of}")
            if not cfg.keep_all_on_duplicate:
                stats.rejected += 1
                rejected_rows.append(
                    {
                        "Row #": row_no,
                        "Reason": f"duplicate of row {duplicate_of} ({duplicate_why})",
                        **record,
                    }
                )
                continue

        if email_value:
            seen_email.setdefault(email_value, row_no)
        if phone_value:
            seen_phone.setdefault(phone_value, row_no)
        seen_row.setdefault(row_key, row_no)
        kept_rows.append(record)

    stats.kept = len(kept_rows)

    cleaned = pd.DataFrame(kept_rows, columns=columns)
    rejected = pd.DataFrame(rejected_rows, columns=["Row #", "Reason", *columns])
    return CleanResult(cleaned, rejected, stats, mapping, duplicate_examples)
