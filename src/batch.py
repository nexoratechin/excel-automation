"""Batch mode: clean every spreadsheet inside a ZIP archive.

A monthly client rarely sends one file - they send a folder of them. This module
takes the archive, runs the normal single-file pipeline on each entry, and hands
back one ZIP containing every cleaned workbook plus a summary.

No file is ever extracted to disk, so a malicious path inside the archive
(``../../evil.xlsx``) has nothing to escape into.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import ConfigError
from .webapp_core import MAX_BYTES, process_file

MAX_FILES = 20
MAX_TOTAL_BYTES = 60 * 1024 * 1024
TABLE_SUFFIXES = {".xlsx", ".xlsm", ".csv"}
# Files the OS or Excel leaves behind that a client should never be charged for.
JUNK_NAMES = {".ds_store", "thumbs.db", "desktop.ini"}


@dataclass
class FileOutcome:
    name: str
    ok: bool = True
    rows_in: int = 0
    kept: int = 0
    rejected: int = 0
    duplicates: int = 0
    bad_emails: int = 0
    bad_phones: int = 0
    changes: int = 0
    error: str = ""


@dataclass
class BatchResult:
    outcomes: list[FileOutcome] = field(default_factory=list)
    archive: bytes = b""
    kept_total: int = 0
    rejected_total: int = 0
    changes_total: int = 0
    files_ok: int = 0
    files_failed: int = 0

    @property
    def summary_frame(self) -> pd.DataFrame:
        rows = [
            {
                "File": o.name,
                "Status": "cleaned" if o.ok else f"failed: {o.error}",
                "Rows in": o.rows_in,
                "Kept": o.kept,
                "Rejected": o.rejected,
                "Duplicates": o.duplicates,
                "Bad emails": o.bad_emails,
                "Bad phones": o.bad_phones,
                "Cells cleaned": o.changes,
            }
            for o in self.outcomes
        ]
        return pd.DataFrame(rows)


def _is_candidate(info: zipfile.ZipInfo) -> bool:
    if info.is_dir():
        return False
    name = info.filename
    base = Path(name).name
    if not base or base.startswith(".") or base.lower() in JUNK_NAMES:
        return False
    if "__MACOSX" in Path(name).parts:
        return False
    return Path(name).suffix.lower() in TABLE_SUFFIXES


def process_zip(data: bytes, filename: str = "upload.zip", **settings) -> BatchResult:
    """Clean every spreadsheet in ``data``. Raises ConfigError if unusable."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ConfigError("That ZIP file is damaged or not a real ZIP.") from exc

    with archive:
        members = [i for i in archive.infolist() if _is_candidate(i)]

        if not members:
            raise ConfigError(
                "No Excel or CSV files were found inside that ZIP. "
                "Add .xlsx or .csv files and try again."
            )
        if len(members) > MAX_FILES:
            raise ConfigError(
                f"That ZIP holds {len(members)} files. The limit is {MAX_FILES} per "
                "upload - split it into smaller batches."
            )
        if sum(i.file_size for i in members) > MAX_TOTAL_BYTES:
            raise ConfigError(
                "That ZIP is too large once unpacked (over 60 MB). "
                "Split it into smaller batches."
            )

        result = BatchResult()
        used_names: set[str] = set()
        outputs: list[tuple[str, bytes]] = []

        for info in sorted(members, key=lambda i: i.filename.lower()):
            label = Path(info.filename).name
            outcome = FileOutcome(name=label)
            try:
                if info.file_size > MAX_BYTES:
                    raise ConfigError("file is over 15 MB")
                payload = archive.read(info)
                single = process_file(payload, label, **settings)
            except ConfigError as exc:
                outcome.ok = False
                outcome.error = str(exc)
            except Exception:  # noqa: BLE001 - one bad file must not stop the batch
                outcome.ok = False
                outcome.error = "could not be read; it may be password protected"
            else:
                s = single.stats
                outcome.rows_in = s.total_rows
                outcome.kept = single.cleaned_total
                outcome.rejected = single.rejected_total
                outcome.duplicates = s.duplicates_removed
                outcome.bad_emails = s.invalid_email
                outcome.bad_phones = s.invalid_phone
                outcome.changes = single.changes_total
                result.kept_total += single.cleaned_total
                result.rejected_total += single.rejected_total
                result.changes_total += single.changes_total
                result.files_ok += 1

                out_name = _unique(f"{Path(label).stem}_cleaned.xlsx", used_names)
                outputs.append((out_name, single.workbook))

            if not outcome.ok:
                result.files_failed += 1
            result.outcomes.append(outcome)

    if not outputs:
        raise ConfigError(
            "None of the files in that ZIP could be read. "
            "The first problem was: " + (result.outcomes[0].error or "unknown")
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as out:
        for name, payload in outputs:
            out.writestr(name, payload)
        csv = result.summary_frame.to_csv(index=False).encode("utf-8-sig")
        out.writestr("batch_summary.csv", csv)

    result.archive = buffer.getvalue()
    return result


def _unique(name: str, used: set[str]) -> str:
    """Two folders can hold files with the same name; keep both."""
    if name not in used:
        used.add(name)
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 2
    while f"{stem} ({counter}){suffix}" in used:
        counter += 1
    final = f"{stem} ({counter}){suffix}"
    used.add(final)
    return final


def zip_name_for(filename: str) -> str:
    stem = Path(filename).stem
    if not stem or stem.startswith("."):
        stem = "batch"
    return f"{stem}_cleaned.zip"
