"""Fixtures for the end to end tests: a real browser against a running app."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import Browser, Page, sync_playwright  # noqa: E402

RESULTS = Path(os.environ.get("E2E_RESULTS", "e2e-results"))


def _url(name: str) -> str:
    value = os.environ.get(name, "").rstrip("/")
    if not value:
        pytest.skip(f"{name} is not set")
    return value


@pytest.fixture(scope="session")
def notes_url() -> str:
    """Base URL of the demo notes app (local or live)."""
    return _url("NOTES_URL")


@pytest.fixture(scope="session")
def dashboard_url() -> str:
    """Base URL of the dashboard service."""
    return _url("DASHBOARD_URL")


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture()
def page(browser: Browser) -> Iterator[Page]:
    context = browser.new_context(viewport={"width": 1000, "height": 700})
    p = context.new_page()
    p.set_default_timeout(10_000)
    RESULTS.mkdir(parents=True, exist_ok=True)
    yield p
    context.close()
