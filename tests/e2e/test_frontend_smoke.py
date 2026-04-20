"""End-to-end smoke tests for the rating UI.

These tests are marked with the `e2e` marker and are excluded from the
default run (see pytest.ini). To execute them:

    # 1. start the app (e.g. `start.bat` or `uvicorn app:app --port 8000`)
    # 2. point the suite at it:
    export BADGER_BASE_URL=http://127.0.0.1:8000   # bash / CI
    set BADGER_BASE_URL=http://127.0.0.1:8000      # Windows cmd
    pytest -m e2e

The first run also needs a one-time browser install:

    playwright install chromium
"""
from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("BADGER_BASE_URL")


@pytest.fixture(autouse=True)
def _require_base_url():
    if not BASE_URL:
        pytest.skip("BADGER_BASE_URL not set; skipping e2e frontend smoke tests")


def test_index_page_loads(page):
    page.goto(BASE_URL)
    # The dashboard mounts the main app script; confirm the page rendered
    # without a hard error before asserting anything rating-specific.
    assert page.title() != ""


def test_no_console_errors_on_index(page):
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on(
        "console",
        lambda msg: errors.append(msg.text) if msg.type == "error" else None,
    )
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    assert not errors, f"Console/page errors on load: {errors}"
