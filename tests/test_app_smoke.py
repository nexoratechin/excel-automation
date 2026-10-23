"""Smoke test for the Streamlit front end.

Skipped automatically when Streamlit is not installed, so the core test suite
still runs on a plain pandas + openpyxl setup.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="web app dependencies are not installed")

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def run_app() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=60).run()


def test_app_starts_without_exception():
    app = run_app()
    assert not app.exception, [e.value for e in app.exception]


def test_app_shows_the_upload_prompt():
    app = run_app()
    text = " ".join(m.value for m in app.markdown) + " ".join(i.value for i in app.info)
    assert "Clean my Excel list" in " ".join(t.value for t in app.title)
    assert "How it works" in text


def test_app_offers_the_sample_file():
    app = run_app()
    labels = [str(button.label) for button in app.get("download_button")]
    assert any("sample" in label.lower() for label in labels)
