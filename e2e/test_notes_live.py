"""Post-deploy checks of the summary strip, run by e2e_live against the deployed app.

These need the notes the test adds itself and the live page, so they run after the deploy and are
not part of the pre-merge e2e_local job (see docs/e2e.md).
"""

from __future__ import annotations

import re
import uuid

from playwright.sync_api import Page, expect


def _add(page: Page, text: str) -> None:
    page.fill("#t", text)
    page.click("button")
    expect(page.locator("#n li", has_text=text)).to_be_visible()


def _channels(css: str) -> tuple[int, ...]:
    return tuple(int(v) for v in re.findall(r"\d+", css)[:3])


def test_the_summary_counts_the_notes_in_the_list(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    _add(page, f"count {uuid.uuid4().hex[:8]}")
    shown = page.locator("#n li").count()
    expect(page.locator("#stats")).to_have_text(
        re.compile(rf"^{shown} notes, longest \d+ characters$")
    )


def test_clear_all_empties_the_list(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    _add(page, f"clear {uuid.uuid4().hex[:8]}")
    page.click("#clear")
    expect(page.locator("#n li")).to_have_count(0)


def test_the_hint_is_readable_against_its_background(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    colour = page.evaluate("getComputedStyle(document.querySelector('.hint')).color")
    background = page.evaluate("getComputedStyle(document.querySelector('main')).backgroundColor")
    assert _channels(colour) != _channels(background), f"hint {colour} on {background}"
