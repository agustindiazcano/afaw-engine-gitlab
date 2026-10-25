"""Behaviour and appearance of the demo notes app, as a user sees it."""

from __future__ import annotations

import uuid

from playwright.sync_api import Page, expect

from e2e.conftest import RESULTS

BRAND = "rgb(11, 95, 255)"
WHITE = "rgb(255, 255, 255)"


def test_a_note_added_in_the_page_appears_in_the_list(page: Page, notes_url: str) -> None:
    text = f"e2e {uuid.uuid4().hex[:8]}"
    page.goto(notes_url)
    page.fill("#t", text)
    page.click("button")
    expect(page.locator("#n li", has_text=text)).to_be_visible()


def test_a_blank_note_is_not_added(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    expect(page.locator("#v")).not_to_be_empty()
    before = page.locator("#n li").count()
    page.fill("#t", "   ")
    page.click("button")
    page.wait_for_timeout(500)
    assert page.locator("#n li").count() == before


def test_the_page_shows_the_release_and_the_commit(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    expect(page.locator("#v")).to_contain_text("commit")


def test_the_add_button_has_the_brand_colours(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    button = page.locator("button")
    expect(button).to_have_css("background-color", BRAND)
    expect(button).to_have_css("color", WHITE)
    page.screenshot(path=str(RESULTS / "notes-app.png"))
