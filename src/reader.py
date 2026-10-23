"""Read .xlsx / .csv into a DataFrame without losing data to type coercion."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from .config import ConfigError


def list_sheets(path: str | Path) -> list[str]:
    """Sheet names in an Excel workbook (empty list for csv)."""
    p = Path(path)
    if p.suffix.lower() in {".csv", ".txt", ".tsv"}:
        return []
    with pd.ExcelFile(p, engine="openpyxl") as book:
        return list(book.sheet_names)


def read_table(path: str | Path, sheet: str | int | None = None, header_row: int = 1) -> pd.DataFrame:
    """Load a table, keeping every cell as text.

    dtype=str is the important part: it stops pandas turning phone numbers into
    floats (9.87654E+09) and stripping leading zeros from pin codes.
    """
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Input file not found: {p}")

    suffix = p.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        engine = "openpyxl" if suffix != ".xls" else None
        try:
            df = pd.read_excel(
                p, sheet_name=sheet, header=header_row - 1, dtype=str, engine=engine
            )
        except ValueError as exc:
            sheets = list_sheets(p)
            raise ConfigError(
                f"Could not read sheet {sheet!r} from {p.name}. "
                f"Available sheets: {', '.join(sheets) or 'none'}"
            ) from exc
        if isinstance(df, dict):  # pandas returns a dict only when sheet_name=None
            first = next(iter(df))
            df = df[first]
        return _tidy_frame(df)

    if suffix in {".csv", ".txt", ".tsv"}:
        return _tidy_frame(_read_csv(p, header_row))
    if suffix == ".xls":
        raise ConfigError("Legacy .xls files need xlrd installed. Save as .xlsx first.")
    raise ConfigError(
        f"Unsupported file type '{suffix}'. Use .xlsx, .xlsm or .csv."
    )


def _read_csv(path: Path, header_row: int) -> pd.DataFrame:
    """Try sensible encodings, then sniff the delimiter."""
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as fh:
                sample = fh.read(8192)
                fh.seek(0)
                dialect = _sniff(sample)
                return _parse_csv(fh, dialect.delimiter, header_row)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    raise ConfigError(f"Could not decode {path.name}: {last_error}")


def _parse_csv(handle, delimiter: str, header_row: int) -> pd.DataFrame:
    """Parse with the fast C engine first, then pandas' stricter Python engine.

    A stray quote such as ``"Rahul" Sharma`` is accepted by the C engine and
    rejected by the Python engine (``',' expected after '"'``), so trying C
    first turns a hard failure into a normal read.
    """
    parser_error: Exception | None = None
    for engine in ("c", "python"):
        handle.seek(0)
        try:
            return pd.read_csv(
                handle,
                sep=delimiter,
                header=header_row - 1,
                dtype=str,
                skip_blank_lines=True,
                engine=engine,
            )
        except pd.errors.EmptyDataError as exc:
            raise ConfigError("That file is empty - there is nothing to clean.") from exc
        except pd.errors.ParserError as exc:
            parser_error = exc
            continue

    raise ConfigError(
        "This CSV file could not be read. A quote mark in the wrong place breaks "
        "the whole file, and neither reader could recover it.\n\n"
        "Fix: open it in Excel and use File > Save As > Excel Workbook (.xlsx). "
        "Excel files never have this problem."
    ) from parser_error


def _sniff(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        class _Comma(csv.excel):
            delimiter = ","
        return _Comma


def _tidy_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Drop fully empty rows/columns and unwrap MultiIndex headers."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join(str(p) for p in col if str(p) != "nan").strip() for col in df.columns]

    # Blank rows are left in place: cleaner.clean() counts and drops them, so the
    # report can tell the client how many empty rows were in their file.
    df = df.loc[:, ~df.columns.astype(str).str.fullmatch(r"Unnamed: \d+")]
    df.columns = [str(c).strip() for c in df.columns]
    # Normalise every remaining hole to "" so downstream code only sees text.
    df = df.astype(object).where(df.notna(), "")
    return df.reset_index(drop=True)


def resolve_column(df: pd.DataFrame, wanted: str, role: str) -> str:
    """Find the real column name, tolerating case / spacing / stray punctuation."""
    available = [str(c) for c in df.columns]
    if wanted in available:
        return wanted

    def key(text: str) -> str:
        return "".join(ch for ch in text.lower() if ch.isalnum())

    target = key(wanted)
    matches = [c for c in available if key(c) == target]
    if len(matches) == 1:
        return matches[0]

    raise ConfigError(
        f"Column {wanted!r} (for {role}) not found.\n"
        f"Columns in this file: {', '.join(available) or 'none'}\n"
        f"Tip: pass the exact header name, e.g. --email-col \"Email Address\""
    )


EMAIL_HINTS = ("email", "emailaddress", "mailid", "emailid", "mail")
PHONE_HINTS = ("mobile", "mobileno", "mobilenumber", "phone", "phoneno", "phonenumber",
               "contact", "contactno", "contactnumber", "whatsapp", "cell", "cellno")


def _key(text: str) -> str:
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def guess_column(columns, hints: tuple[str, ...]) -> str | None:
    """Pick the most likely column by header keywords (fallback only)."""
    best: tuple[int, str] | None = None
    for col in columns:
        col_key = _key(col)
        score = sum(len(h) for h in hints if h in col_key)
        if score and (best is None or score > best[0]):
            best = (score, str(col))
    return best[1] if best else None


def guess_columns(
    df: pd.DataFrame,
    country: str = "IN",
    phone_format: str = "local",
    threshold: float = 0.5,
    sample: int = 300,
) -> tuple[str | None, str | None]:
    """Detect the email and phone columns from their *contents*.

    Header names lie: a "Contact Person" column is not a phone column, and
    "Email" columns are sometimes full of unusable values. Sampling the cells
    and requiring that most of them validate is far more reliable than guessing
    from the label, with header keywords used only as a tie-breaker/fallback.
    """
    from .validators import clean_text, normalize_email, normalize_phone

    def rate(col: str, kind: str) -> float:
        raw = [clean_text(v) for v in df[col].tolist()]
        values = [v for v in raw if v][:sample]
        if len(values) < 3:
            return 0.0
        if kind == "email":
            hits = sum(1 for v in values if normalize_email(v)[0])
        else:
            hits = sum(1 for v in values if normalize_phone(v, country, phone_format)[0])
        return hits / len(values)

    def best(kind: str, hints: tuple[str, ...]) -> str | None:
        scored = [(_key_tiebreak(col, hints), rate(col, kind), str(col)) for col in df.columns]
        scored = [s for s in scored if s[1] >= threshold]
        if scored:
            scored.sort(key=lambda s: (s[1], s[0]), reverse=True)
            return scored[0][2]
        return guess_column(df.columns, hints)

    return best("email", EMAIL_HINTS), best("phone", PHONE_HINTS)


def _key_tiebreak(col, hints: tuple[str, ...]) -> int:
    col_key = _key(col)
    return sum(1 for h in hints if h in col_key)


GSTIN_HINTS = ("gstin", "gstno", "gstnumber", "gst")
PAN_HINTS = ("panno", "pannumber", "pan")
PINCODE_HINTS = ("pincode", "postalcode", "zip", "pin")


def guess_business_columns(
    df: pd.DataFrame, threshold: float = 0.6, sample: int = 300
) -> tuple[str | None, str | None, str | None]:
    """Find GSTIN, PAN and pincode columns.

    Both the header and the contents must agree. Relying on either alone is
    unsafe: "Company" contains "pan", and a column of six-digit order IDs looks
    exactly like pincodes -- either mistake would reject good rows.
    """
    from .validators import clean_text, normalize_gstin, normalize_pan, normalize_pincode

    def best(check, hints: tuple[str, ...]) -> str | None:
        winner: tuple[float, str] | None = None
        for col in df.columns:
            if not any(h in _key(col) for h in hints):
                continue
            values = [clean_text(v) for v in df[col].tolist()]
            values = [v for v in values if v][:sample]
            if len(values) < 3:
                continue
            rate = sum(1 for v in values if check(v)[0]) / len(values)
            if rate >= threshold and (winner is None or rate > winner[0]):
                winner = (rate, str(col))
        return winner[1] if winner else None

    return (
        best(normalize_gstin, GSTIN_HINTS),
        best(normalize_pan, PAN_HINTS),
        best(normalize_pincode, PINCODE_HINTS),
    )
