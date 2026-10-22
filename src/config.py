"""Configuration objects for the cleaner.

Everything a customer might need to change lives here, not in the cleaning
logic, so the same code works on every client file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

VALID_COUNTRIES = ("IN", "US", "ANY")
VALID_PHONE_FORMATS = ("local", "e164", "digits")


class ConfigError(Exception):
    """Raised when the user configuration is unusable."""


@dataclass
class Config:
    # Input / output
    input_path: str = ""
    output_path: str = ""
    sheet: str | int | None = None
    header_row: int = 1

    # Column mapping (exact header names in the source file)
    email_col: str | None = None
    phone_col: str | None = None
    name_col: str | None = None

    # Columns that must be present and non-empty for a row to survive
    required: list[str] = field(default_factory=list)

    # Validation
    country: str = "IN"
    phone_format: str = "local"

    # Behaviour
    drop_blank_rows: bool = True
    keep_all_on_duplicate: bool = False

    def validate(self) -> None:
        if not self.input_path:
            raise ConfigError("No input file given. Use --input <file.xlsx>.")
        if not self.output_path:
            raise ConfigError("No output file given. Use --out <file.xlsx>.")

        src = Path(self.input_path).resolve()
        out = Path(self.output_path).resolve()
        if src == out:
            raise ConfigError(
                "Output path is the same as the input file. "
                "This tool never modifies your original file - pick another --out."
            )

        self.country = self.country.upper()
        if self.country not in VALID_COUNTRIES:
            raise ConfigError(
                f"Unknown country '{self.country}'. Choose one of: {', '.join(VALID_COUNTRIES)}"
            )
        if self.phone_format not in VALID_PHONE_FORMATS:
            raise ConfigError(
                f"Unknown phone format '{self.phone_format}'. "
                f"Choose one of: {', '.join(VALID_PHONE_FORMATS)}"
            )
        if self.header_row < 1:
            raise ConfigError("--header-row must be 1 or greater.")

        if not str(self.output_path).lower().endswith(".xlsx"):
            raise ConfigError("Output must be an .xlsx file (the report needs multiple sheets).")

        if not src.exists():
            raise ConfigError(f"Input file not found: {self.input_path}")

    @property
    def available_columns(self) -> list[str]:
        return list(self.required) + [
            c for c in (self.email_col, self.phone_col, self.name_col) if c
        ]


def load_config_file(path: str | Path) -> dict:
    """Read a JSON config file into a plain dict of Config kwargs."""
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file is not valid JSON ({path}): {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Config file must contain a JSON object: {path}")

    for alias, target in (("input", "input_path"), ("out", "output_path"), ("sheet_name", "sheet")):
        if alias in raw:
            raw.setdefault(target, raw.pop(alias))

    allowed = set(Config.__dataclass_fields__)
    unknown = set(raw) - allowed
    if unknown:
        raise ConfigError(
            f"Unknown config key(s): {', '.join(sorted(unknown))}. "
            f"Allowed keys: {', '.join(sorted(allowed))}"
        )
    if "required" in raw and isinstance(raw["required"], str):
        raw["required"] = [c.strip() for c in raw["required"].split(",") if c.strip()]
    return raw


def build_config(cli_values: dict, file_values: dict) -> Config:
    """Build a Config from a JSON file plus the CLI flags the user typed.

    ``cli_values`` must contain *only* explicitly typed flags, so that anything
    the user did not type can still come from the file.
    """
    merged = {k: v for k, v in file_values.items() if v not in (None, "")}
    merged.update({k: v for k, v in cli_values.items() if v is not None})
    return Config(**merged)
