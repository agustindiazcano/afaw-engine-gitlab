"""The dashboard as a visitor sees it: navigation, charts, the demo banner and the live panel."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from e2e.conftest import RESULTS


def test_the_experiments_page_draws_three_charts(page: Page, dashboard_url: str) -> None:
    page.goto(dashboard_url + "/")
    page.click("nav a.item[href='/experiments/']")
    expect(page.locator("h1")).to_contain_text("Experiments")
    assert page.locator("main svg.bars").count() >= 3
    page.screenshot(path=str(RESULTS / "experiments.png"), full_page=True)


def test_the_demo_page_says_its_data_is_invented(page: Page, dashboard_url: str) -> None:
    page.goto(dashboard_url + "/demo/")
    expect(page.locator("p.banner")).to_contain_text("invented")


def test_the_live_panel_fills_in_within_ten_seconds(page: Page, dashboard_url: str) -> None:
    page.goto(dashboard_url + "/")
    expect(page.locator("#live-stamp")).not_to_be_empty(timeout=10_000)
    page.screenshot(path=str(RESULTS / "dashboard.png"), full_page=True)
