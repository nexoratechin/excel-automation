"""Web front end: upload an Excel file, get the cleaned file back.

    streamlit run app.py

The cleaning itself lives in src/, so this file is only widgets and wording.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st

from src.batch import MAX_FILES, process_zip, zip_name_for
from src.config import ConfigError
from src.webapp_core import MAX_BYTES, inspect_file, process_file

SAMPLE = Path("data/sample_dirty.xlsx")

COUNTRIES = {"India (IN)": "IN", "United States (US)": "US", "Any country": "ANY"}
COUNTRY_LABELS = list(COUNTRIES)
FORMATS = {
    "10 digits (9876543210)": "local",
    "International (+919876543210)": "e164",
    "Digits only": "digits",
}
FORMAT_LABELS = list(FORMATS)

st.set_page_config(
    page_title="Excel Cleanup | Nexora Tech",
    page_icon=":material/table_view:",
    layout="centered",
)

st.title("Clean my Excel list")
st.caption(
    "Removes duplicate contacts, fixes invalid emails and phone numbers, and "
    "sends back a report. Your original file is never changed."
)


@st.cache_data(show_spinner=False, max_entries=8)
def cached_inspect(data: bytes, filename: str, header_row: int = 1) -> object:
    return inspect_file(data, filename, header_row)


def reset_result() -> None:
    st.session_state.pop("result", None)
    st.session_state.pop("batch", None)
    st.session_state.pop("result_for", None)
    st.session_state.pop("result_note", None)


def render_batch(data: bytes, filename: str, fingerprint: str) -> None:
    """One ZIP in, one ZIP of cleaned workbooks out."""
    st.info(
        f"**Batch mode.** Every `.xlsx` and `.csv` inside the ZIP is cleaned with "
        f"the same rules — up to {MAX_FILES} files. Columns are detected per file, "
        "so folders with different layouts all work."
    )

    with st.form("batch_settings"):
        left, right = st.columns(2)
        with left:
            country_label = st.selectbox("Phone numbers are from", COUNTRY_LABELS)
        with right:
            format_label = st.selectbox("Write phone numbers as", FORMAT_LABELS)
        submitted = st.form_submit_button(
            "Clean all files", type="primary", width="stretch"
        )

    if submitted:
        reset_result()
        with st.spinner("Cleaning every file..."):
            try:
                result = process_zip(
                    data,
                    filename,
                    country=COUNTRIES[country_label],
                    phone_format=FORMATS[format_label],
                )
            except ConfigError as exc:
                st.error(str(exc))
                st.stop()
            except Exception:  # noqa: BLE001 - never show a stack trace to a client
                st.error("Something went wrong reading that ZIP. Please send it to me directly.")
                st.stop()
        st.session_state["batch"] = result
        st.session_state["result_for"] = fingerprint

    result = st.session_state.get("batch")
    if result is None:
        return

    st.divider()
    st.subheader("Batch finished")

    first, second, third, fourth = st.columns(4)
    first.metric("Files cleaned", f"{result.files_ok} / {len(result.outcomes)}")
    second.metric("Rows kept", f"{result.kept_total:,}")
    third.metric("Rows rejected", f"{result.rejected_total:,}")
    fourth.metric("Cells cleaned", f"{result.changes_total:,}")

    if result.files_failed:
        st.warning(
            f"{result.files_failed} file(s) could not be read and were skipped. "
            "They are marked in the table below."
        )

    st.dataframe(result.summary_frame, width="stretch", hide_index=True)

    st.download_button(
        f"Download all {result.files_ok} cleaned files",
        result.archive,
        file_name=zip_name_for(filename),
        mime="application/zip",
        type="primary",
        width="stretch",
    )
    st.caption(
        "The ZIP contains one workbook per input file, plus **batch_summary.csv** "
        "with the same numbers shown above."
    )


uploaded = st.file_uploader(
    "Upload your contact list",
    type=["xlsx", "xlsm", "csv", "zip"],
    help=(
        f"Excel or CSV up to {MAX_BYTES // (1024 * 1024)} MB, "
        f"or a ZIP holding up to {MAX_FILES} files."
    ),
)

if uploaded is None:
    st.info(
        "**How it works**  \n"
        "1. Upload your file, or a ZIP of several files.  \n"
        "2. Check the detected columns.  \n"
        "3. Download the cleaned file and the report."
    )
    if SAMPLE.exists():
        st.download_button(
            "Try it with a sample messy file",
            SAMPLE.read_bytes(),
            file_name="sample_dirty.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    st.stop()

data = uploaded.getvalue()
# The filename is not enough: clients upload "contacts.xlsx" every month, and a
# stale result must never be offered for a different file with the same name.
fingerprint = hashlib.sha256(data).hexdigest()[:16]

if uploaded.name.lower().endswith(".zip"):
    render_batch(data, uploaded.name, fingerprint)
    st.stop()

with st.expander("My column headers are not on row 1"):
    header_row = int(
        st.number_input(
            "Header row",
            min_value=1,
            max_value=50,
            value=1,
            help="Leave at 1 unless there is a title or logo row above the headers.",
        )
    )

try:
    info = cached_inspect(data, uploaded.name, header_row)
except ConfigError as exc:
    st.error(str(exc))
    st.stop()

if st.session_state.get("result_for") not in (None, fingerprint):
    reset_result()

st.success(
    f"Read **{info.row_count:,} rows** and **{len(info.columns)} columns** "
    f"from `{uploaded.name}`."
)

with st.expander("Look at the first rows"):
    st.dataframe(info.preview, width="stretch", hide_index=True)

options = ["(none)"] + list(info.columns)
email_index = options.index(info.email_guess) if info.email_guess in options else 0
phone_index = options.index(info.phone_guess) if info.phone_guess in options else 0

with st.form("settings"):
    st.subheader("Check the columns")
    left, right = st.columns(2)
    with left:
        email_choice = st.selectbox("Email column", options, index=email_index)
    with right:
        phone_choice = st.selectbox("Phone column", options, index=phone_index)

    required = st.multiselect(
        "Columns that must never be empty",
        list(info.columns),
        default=[c for c in info.columns if c.lower().strip() == "name"],
        help="Rows missing these will be moved to the Rejected sheet. Leave empty to allow blanks.",
    )

    left, right = st.columns(2)
    with left:
        country_label = st.selectbox("Phone numbers are from", COUNTRY_LABELS)
    with right:
        format_label = st.selectbox("Write phone numbers as", FORMAT_LABELS)

    keep_duplicates = st.checkbox(
        "Only report duplicates, do not remove them", value=False
    )

    submitted = st.form_submit_button(
        "Clean this file", type="primary", width="stretch"
    )

if submitted:
    reset_result()
    country = COUNTRIES[country_label]
    phone_format = FORMATS[format_label]

    with st.spinner("Cleaning your file..."):
        try:
            result = process_file(
                data,
                uploaded.name,
                email_col=None if email_choice == "(none)" else email_choice,
                phone_col=None if phone_choice == "(none)" else phone_choice,
                required=required,
                country=country,
                phone_format=phone_format,
                keep_duplicates=keep_duplicates,
                header_row=header_row,
            )
        except ConfigError as exc:
            st.error(str(exc))
            st.stop()
        except Exception:  # noqa: BLE001 - never show a stack trace to a client
            st.error(
                "Something went wrong reading that file. It may be password "
                "protected or saved in an unusual format. Please send it to me directly."
            )
            st.stop()

    st.session_state["result"] = result
    st.session_state["result_for"] = fingerprint
    note = []
    if result.email_col:
        note.append(f"emails from '{result.email_col}'")
    if result.phone_col:
        note.append(f"phones from '{result.phone_col}'")
    st.session_state["result_note"] = ", ".join(note)

result = st.session_state.get("result")
if result is not None:
    st.divider()
    st.subheader("Done")
    if st.session_state.get("result_note"):
        st.caption(f"Checked {st.session_state['result_note']}. Original file untouched.")

    s = result.stats
    first, second, third, fourth = st.columns(4)
    first.metric("Clean rows", f"{result.cleaned_total:,}")
    second.metric("Duplicates", f"{s.duplicates_removed:,}")
    third.metric("Bad emails", f"{s.invalid_email:,}")
    fourth.metric("Bad phones", f"{s.invalid_phone:,}")

    st.download_button(
        "Download cleaned file",
        result.workbook,
        file_name=f"{Path(uploaded.name).stem}_cleaned.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        width="stretch",
    )

    if result.changes_total:
        with st.expander(f"See the {result.changes_total:,} cells that were cleaned"):
            st.caption(
                "Every fix is shown before and after, and listed on the "
                "**Changes** sheet in the downloaded file."
            )
            st.dataframe(result.changes_preview, width="stretch", hide_index=True)

    if result.rejected_total:
        with st.expander(f"See the {result.rejected_total:,} rejected rows"):
            st.caption(
                "Nothing was deleted silently. Every one of these is on the "
                "Rejected sheet in the downloaded file, with its reason."
            )
            st.dataframe(result.rejected_preview, width="stretch", hide_index=True)
    else:
        st.info("No rows were rejected. Your file was already clean.")

    st.caption(
        "The downloaded file has four sheets: **Report**, **Cleaned**, "
        "**Rejected** and **Changes**."
    )

st.divider()
st.caption(
    "Questions or a file over 15 MB? Message me and I will handle it directly."
)
