"""Logic behind the web app, kept free of Streamlit so it can be tested.

The web layer only handles widgets and messages; everything that touches a file
happens here.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .cleaner import Stats, clean
from .config import Config, ConfigError
from .reader import guess_columns, read_table
from .report import write_workbook

ALLOWED_SUFFIXES = {".xlsx", ".xlsm", ".csv", ".txt", ".tsv"}
MAX_BYTES = 15 * 1024 * 1024


@dataclass
class InspectResult:
    columns: list[str]
    email_guess: str | None
    phone_guess: str | None
    preview: pd.DataFrame
    row_count: int


@dataclass
class ProcessResult:
    stats: Stats
    workbook: bytes
    email_col: str | None
    phone_col: str | None
    cleaned_preview: pd.DataFrame
    rejected_preview: pd.DataFrame
    changes_preview: pd.DataFrame
    cleaned_total: int
    rejected_total: int
    changes_total: int


def _check(data: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ConfigError(
            f"'{suffix or filename}' is not a supported file. "
            "Please upload an .xlsx, .xlsm or .csv file."
        )
    if not data:
        raise ConfigError("That file is empty.")
    if len(data) > MAX_BYTES:
        raise ConfigError(
            "That file is larger than 15 MB. Please contact me directly and "
            "I will process it manually."
        )
    return suffix


def _read(data: bytes, filename: str, header_row: int) -> pd.DataFrame:
    suffix = _check(data, filename)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / f"input{suffix}"
        path.write_bytes(data)
        df = read_table(path, None, header_row)
    if df.empty:
        raise ConfigError(
            "No data rows were found. Check that row 1 contains your column headers."
        )
    return df


def inspect_file(data: bytes, filename: str, header_row: int = 1) -> InspectResult:
    """Read the file and suggest columns, without cleaning anything."""
    df = _read(data, filename, header_row)
    email_guess, phone_guess = guess_columns(df, "IN", "local")
    return InspectResult(
        columns=[str(c) for c in df.columns],
        email_guess=email_guess,
        phone_guess=phone_guess,
        preview=df.head(5),
        row_count=len(df),
    )


def process_file(
    data: bytes,
    filename: str,
    *,
    email_col: str | None = None,
    phone_col: str | None = None,
    required: list[str] | None = None,
    country: str = "IN",
    phone_format: str = "local",
    keep_duplicates: bool = False,
    keep_blank_rows: bool = False,
    header_row: int = 1,
) -> ProcessResult:
    """Clean an uploaded file and return the finished workbook as bytes."""
    df = _read(data, filename, header_row)

    cfg = Config(
        # Kept only as a label, so the report shows the name the client knows.
        input_path=filename,
        output_path="cleaned.xlsx",
        header_row=header_row,
        email_col=email_col or None,
        phone_col=phone_col or None,
        required=list(required or []),
        country=country,
        phone_format=phone_format,
        keep_all_on_duplicate=keep_duplicates,
        drop_blank_rows=not keep_blank_rows,
    )

    if cfg.email_col is None or cfg.phone_col is None:
        guess_email, guess_phone = guess_columns(df, country, phone_format)
        cfg.email_col = cfg.email_col or guess_email
        cfg.phone_col = cfg.phone_col or guess_phone

    result = clean(df, cfg)

    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / (Path(filename).stem + "_cleaned.xlsx")
        write_workbook(result, cfg, out)
        payload = out.read_bytes()

    return ProcessResult(
        stats=result.stats,
        workbook=payload,
        email_col=cfg.email_col,
        phone_col=cfg.phone_col,
        cleaned_preview=result.cleaned.head(10),
        rejected_preview=result.rejected.head(50),
        changes_preview=result.changes.head(50),
        cleaned_total=len(result.cleaned),
        rejected_total=len(result.rejected),
        changes_total=len(result.changes),
    )

__all__ = ["InspectResult", "ProcessResult", "inspect_file", "process_file", "MAX_BYTES"]
