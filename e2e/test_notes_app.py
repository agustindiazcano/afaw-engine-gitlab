"""Behaviour and appearance of the demo notes app, as a user sees it."""

from __future__ import annotations

import uuid

from playwright.sync_api import Page, Route, expect

from e2e.conftest import RESULTS

BRAND = "rgb(11, 95, 255)"
WHITE = "rgb(255, 255, 255)"


def test_a_note_added_in_the_page_appears_in_the_list(page: Page, notes_url: str) -> None:
    text = f"e2e {uuid.uuid4().hex[:8]}"
    page.goto(notes_url)
    page.fill("#t", text)
    page.click("button")
    expect(page.locator("#n li", has_text=text)).to_be_visible()


def test_a_blank_note_cannot_be_added(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    expect(page.locator("#v")).not_to_be_empty()
    expect(page.locator("button")).to_be_disabled()
    page.fill("#t", "   ")
    expect(page.locator("button")).to_be_disabled()


def test_the_page_shows_the_release_and_the_commit(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    expect(page.locator("#v")).to_contain_text("commit")


def test_the_add_button_has_the_brand_colours(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    button = page.locator("button")
    expect(button).to_have_css("background-color", BRAND)
    expect(button).to_have_css("color", WHITE)
    page.screenshot(path=str(RESULTS / "notes-app.png"))


def test_there_is_no_horizontal_scroll_on_a_phone(page: Page, notes_url: str) -> None:
    page.set_viewport_size({"width": 375, "height": 700})
    page.goto(notes_url)
    expect(page.locator("#v")).not_to_be_empty()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_the_dark_theme_changes_the_background(page: Page, notes_url: str) -> None:
    page.emulate_media(color_scheme="light")
    page.goto(notes_url)
    light = page.evaluate("getComputedStyle(document.body).backgroundColor")
    page.screenshot(path=str(RESULTS / "notes-app-light.png"))
    page.emulate_media(color_scheme="dark")
    dark = page.evaluate("getComputedStyle(document.body).backgroundColor")
    page.screenshot(path=str(RESULTS / "notes-app-dark.png"))
    assert light != dark


def test_the_counter_follows_the_typed_text(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    expect(page.locator("#count")).to_have_text("0/200")
    page.fill("#t", "hello")
    expect(page.locator("#count")).to_have_text("5/200")


def test_the_button_is_enabled_only_with_text(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    expect(page.locator("button")).to_be_disabled()
    page.fill("#t", "something")
    expect(page.locator("button")).to_be_enabled()
    page.fill("#t", "")
    expect(page.locator("button")).to_be_disabled()


def test_the_empty_message_is_hidden_once_a_note_exists(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    expect(page.locator("#v")).not_to_be_empty()
    page.fill("#t", f"e2e {uuid.uuid4().hex[:8]}")
    page.click("button")
    expect(page.locator("#n li")).not_to_have_count(0)
    expect(page.locator("#empty")).to_be_hidden()


def test_the_empty_message_is_shown_when_there_are_no_notes(page: Page, notes_url: str) -> None:
    page.route("**/api/notes", lambda route: route.fulfill(json=[]))
    page.goto(notes_url)
    expect(page.locator("#empty")).to_be_visible()
    expect(page.locator("#empty")).to_have_text("No notes yet. Add the first one.")


def test_a_failed_save_shows_an_alert_and_keeps_the_text(page: Page, notes_url: str) -> None:
    def handle(route: Route) -> None:
        if route.request.method == "POST":
            route.fulfill(status=500, body="boom")
        else:
            route.continue_()

    page.route("**/api/notes", handle)
    page.goto(notes_url)
    page.fill("#t", "keep me")
    page.click("button")
    expect(page.get_by_role("alert")).to_be_visible()
    expect(page.locator("#t")).to_have_value("keep me")


def test_a_deleted_note_disappears_and_the_other_remains(page: Page, notes_url: str) -> None:
    keep = f"keep {uuid.uuid4().hex[:8]}"
    drop = f"drop {uuid.uuid4().hex[:8]}"
    page.goto(notes_url)
    for text in (keep, drop):
        page.fill("#t", text)
        page.click("button")
        expect(page.locator("#n li", has_text=text)).to_be_visible()
    page.locator("#n li", has_text=drop).locator(".del").click()
    expect(page.locator("#n li", has_text=drop)).to_have_count(0)
    expect(page.locator("#n li", has_text=keep)).to_be_visible()


def test_the_stats_endpoint_follows_an_add_and_a_delete(page: Page, notes_url: str) -> None:
    text = f"stats {uuid.uuid4().hex[:8]}"
    before = page.request.get(f"{notes_url}/api/stats").json()
    page.goto(notes_url)
    page.fill("#t", text)
    page.click("button")
    expect(page.locator("#n li", has_text=text)).to_be_visible()
    after = page.request.get(f"{notes_url}/api/stats").json()
    assert after["count"] == before["count"] + 1
    assert after["longest"] >= len(text)
    page.locator("#n li", has_text=text).locator(".del").click()
    expect(page.locator("#n li", has_text=text)).to_have_count(0)
    assert page.request.get(f"{notes_url}/api/stats").json()["count"] == before["count"]


def test_the_summary_line_shows_the_count_and_the_longest_note(page: Page, notes_url: str) -> None:
    page.goto(notes_url)
    page.request.delete(f"{notes_url}/api/notes")
    page.reload()
    expect(page.locator("#stats")).to_have_text("0 notes")
    for text in ("a" * 5, "b" * 12):
        page.fill("#t", text)
        page.click("button")
        expect(page.locator("#n li", has_text=text)).to_be_visible()
    expect(page.locator("#stats")).to_have_text("2 notes, longest 12 characters")
    page.locator("#n li", has_text="b" * 12).locator(".del").click()
    expect(page.locator("#stats")).to_have_text("1 notes, longest 5 characters")
    page.click("#clear")
    expect(page.locator("#stats")).to_have_text("0 notes")
