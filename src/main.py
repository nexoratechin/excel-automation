"""Command-line entry point.

    python -m src.main --input data/sample_dirty.xlsx --config config/sample.json

Run with --help for every option.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .cleaner import clean
from .config import ConfigError, build_config, load_config_file
from .reader import guess_business_columns, guess_columns, list_sheets, read_table
from .report import write_workbook
from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="excel-cleaner",
        description="Clean, validate and de-duplicate an Excel or CSV contact list.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m src.main --input raw.xlsx --config config/sample.json --out out/raw_clean.xlsx\n"
            '  python -m src.main --input raw.xlsx --email-col Email --phone-col Phone --out out/raw_clean.xlsx\n'
            "  python -m src.main --input raw.xlsx --list-sheets\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"excel-cleaner {__version__}")

    io = parser.add_argument_group("input and output")
    io.add_argument("--input", help="source .xlsx / .xlsm / .csv file")
    io.add_argument("--out", help="destination .xlsx file (required)")
    io.add_argument("--sheet", help="sheet name or 0-based index (default: first sheet)")
    io.add_argument("--header-row", type=int, help="row containing the headers (default: 1)")
    io.add_argument("--list-sheets", action="store_true", help="print sheet names and exit")

    mapping = parser.add_argument_group("column mapping")
    mapping.add_argument("--email-col", help="header name of the email column")
    mapping.add_argument("--phone-col", help="header name of the phone column")
    mapping.add_argument("--name-col", help="header name of the name column")
    mapping.add_argument("--gstin-col", help="header name of the GSTIN column")
    mapping.add_argument("--pan-col", help="header name of the PAN column")
    mapping.add_argument("--pincode-col", help="header name of the pincode column")
    mapping.add_argument("--required", help="comma-separated columns that must not be empty")

    rules = parser.add_argument_group("validation rules")
    rules.add_argument("--country", choices=["IN", "US", "ANY"], help="phone numbering plan (default: IN)")
    rules.add_argument(
        "--phone-format",
        choices=["local", "e164", "digits"],
        help="how to write valid phones: local (9876543210), e164 (+919876543210), digits",
    )

    behaviour = parser.add_argument_group("behaviour")
    behaviour.add_argument("--config", help="JSON file with any of the options above")
    behaviour.add_argument("--keep-duplicates", action="store_true", help="report duplicates but keep them")
    behaviour.add_argument("--keep-blank-rows", action="store_true", help="keep rows where every cell is empty")
    behaviour.add_argument("--quiet", action="store_true", help="only print errors")

    # SUPPRESS keeps unticked flags out of the namespace, so a value from
    # --config is only overridden when the user actually typed something.
    for action in parser._actions:
        action.default = argparse.SUPPRESS
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "list_sheets", False):
        if not getattr(args, "input", None):
            print("error: --list-sheets needs --input", file=sys.stderr)
            return 2
        try:
            names = list_sheets(args.input)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if not names:
            print("(csv file - single sheet, no sheet names)")
        for i, name in enumerate(names):
            print(f"{i}: {name}")
        return 0

    cli_values = {
        k: v for k, v in vars(args).items() if k not in {"config", "quiet", "list_sheets"}
    }
    cli_values = _normalise_cli(cli_values)

    try:
        file_values = load_config_file(args.config) if getattr(args, "config", None) else {}
        cfg = build_config(cli_values, file_values)
        cfg.validate()
        if isinstance(cfg.sheet, str) and cfg.sheet.isdigit():
            names = list_sheets(cfg.input_path)
            if cfg.sheet not in names:
                cfg.sheet = int(cfg.sheet)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    quiet = getattr(args, "quiet", False)
    started = time.perf_counter()

    try:
        df = read_table(cfg.input_path, cfg.sheet, cfg.header_row)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if df.empty:
        print("error: no data rows found. Check --header-row and --sheet.", file=sys.stderr)
        return 2

    detected: list[str] = []
    if cfg.email_col is None or cfg.phone_col is None:
        guess_email, guess_phone = guess_columns(df, cfg.country, cfg.phone_format)
        if cfg.email_col is None and guess_email:
            cfg.email_col = guess_email
            detected.append(f"email  '{guess_email}'")
        if cfg.phone_col is None and guess_phone:
            cfg.phone_col = guess_phone
            detected.append(f"phone  '{guess_phone}'")

    if cfg.gstin_col is None or cfg.pan_col is None or cfg.pincode_col is None:
        guess_gstin, guess_pan, guess_pin = guess_business_columns(df)
        if cfg.gstin_col is None and guess_gstin:
            cfg.gstin_col = guess_gstin
            detected.append(f"GSTIN  '{guess_gstin}'")
        if cfg.pan_col is None and guess_pan:
            cfg.pan_col = guess_pan
            detected.append(f"PAN    '{guess_pan}'")
        if cfg.pincode_col is None and guess_pin:
            cfg.pincode_col = guess_pin
            detected.append(f"pincode '{guess_pin}'")
    if cfg.email_col is None:
        print(
            "warning: no email column detected - emails were not validated. "
            "Pass --email-col \"Your Column Name\" to enable it.",
            file=sys.stderr,
        )
    if cfg.phone_col is None:
        print(
            "warning: no phone column detected - phone numbers were not validated. "
            "Pass --phone-col \"Your Column Name\" to enable it.",
            file=sys.stderr,
        )

    try:
        result = clean(df, cfg)
    except (ConfigError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        out = write_workbook(result, cfg, cfg.output_path)
    except PermissionError:
        print(
            f"error: cannot write {cfg.output_path}. Is that file open in Excel? Close it and retry.",
            file=sys.stderr,
        )
        return 2

    elapsed = time.perf_counter() - started
    if not quiet:
        _print_summary(result, cfg, out, elapsed, detected)
    return 0


def _normalise_cli(values: dict) -> dict:
    """Translate argparse names and boolean switches into Config fields."""
    out = dict(values)
    if "input" in out:
        out["input_path"] = out.pop("input")
    if "out" in out:
        out["output_path"] = out.pop("out")
    if "required" in out and isinstance(out["required"], str):
        out["required"] = [c.strip() for c in out["required"].split(",") if c.strip()]
    if out.pop("keep_duplicates", False):
        out["keep_all_on_duplicate"] = True
    if out.pop("keep_blank_rows", False):
        out["drop_blank_rows"] = False
    return out


def _print_summary(result, cfg, out: Path, elapsed: float, detected: list[str] | None = None) -> None:
    s = result.stats
    print()
    print("  Excel cleanup finished")
    print("  " + "-" * 44)
    if detected:
        print("  columns detected automatically:")
        for line in detected:
            print(f"    {line}")
    print(f"  rows read        {s.total_rows:>8,}")
    print(f"  rows kept        {s.kept:>8,}")
    print(f"  rows rejected    {s.rejected:>8,}")
    print(f"    duplicates     {s.duplicates_removed:>8,}")
    print(f"    invalid email  {s.invalid_email:>8,}")
    print(f"    invalid phone  {s.invalid_phone:>8,}")
    print(f"    missing fields {s.missing_required:>8,}")
    if s.blank_rows:
        print(f"  blank rows gone  {s.blank_rows:>8,}")
    print("  " + "-" * 44)
    print(f"  written to       {out}")
    print(f"  took             {elapsed:.2f}s")
    print()
    print(f"  Open it and start on the Report sheet.")


if __name__ == "__main__":
    raise SystemExit(main())
