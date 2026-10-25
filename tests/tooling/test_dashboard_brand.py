"""The dashboard carries the project name and logo, the author footer and a live GitLab panel."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from examples import mock_dashboard
from scripts.afaw_state.views import build
from tests.tooling.helpers import AS_OF, make_task

PORTFOLIO = "https://www.agustindiazcano.com/"
API = "https://gitlab.com/api/v4/projects/gitlab-ai-hackathon%2Ftranscend-october-2026%2F43344247%2Fshowcase"


@pytest.fixture(scope="module")
def live() -> str:
    """A dashboard of real data (no demo banner)."""
    tasks = [make_task("task_001", status="done", branch="feat/a")]
    return build(tasks, {}, {}, None, AS_OF)["dashboard.html"]


@pytest.fixture(scope="module")
def html(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = tmp_path_factory.mktemp("demo")
    mock_dashboard.build_demo(out)
    return (out / "index.html").read_text(encoding="utf-8")


def test_the_page_title_is_the_project_name(html: str) -> None:
    assert "<title>AFAW Engine Gitlab" in html


def test_the_nav_has_the_name_and_an_inline_logo(html: str) -> None:
    nav = re.search(r"<nav.*?</nav>", html, re.S)
    assert nav is not None
    body = nav.group(0)
    assert "AFAW Engine Gitlab" in body
    assert "<svg" in body and 'role="img"' in body and "GitLab" in body
    assert "<img" not in body  # nothing is loaded from another site


def test_the_nav_links_to_the_views_and_the_repository(html: str) -> None:
    nav = re.search(r"<nav.*?</nav>", html, re.S)
    assert nav is not None
    for target in ('href="/live/"', 'href="/api/state"', "gitlab.com/gitlab-ai-hackathon"):
        assert target in nav.group(0)


def test_the_footer_names_the_author_and_links_to_the_portfolio(html: str) -> None:
    footer = re.search(r"<footer.*?</footer>", html, re.S)
    assert footer is not None
    body = footer.group(0)
    assert "Agustin Diaz-Cano" in body
    assert f'href="{PORTFOLIO}"' in body
    assert 'rel="noopener' in body


def test_the_live_panel_reads_the_public_gitlab_api_every_thirty_seconds(live: str) -> None:
    assert 'id="live"' in live
    assert API in live
    assert "setInterval" in live and "30000" in live


def test_the_live_panel_never_carries_a_token_and_writes_text_not_markup(live: str) -> None:
    assert "PRIVATE-TOKEN" not in live and "glpat-" not in live
    script = re.search(r"<script>(.*?)</script>", live, re.S)
    assert script is not None
    assert "innerHTML" not in script.group(1)


def test_the_live_panel_has_a_fallback_without_scripts(live: str) -> None:
    assert "<noscript>" in live


def test_the_demo_with_invented_data_never_shows_real_gitlab_data(html: str) -> None:
    assert 'id="live"' not in html and "<script" not in html and API not in html


def test_the_page_has_one_main_landmark_between_the_nav_and_the_footer(html: str) -> None:
    assert html.index("<nav") < html.index("<main") < html.index("<footer")


def test_the_build_is_still_deterministic(tmp_path: Path) -> None:
    mock_dashboard.build_demo(tmp_path / "a")
    mock_dashboard.build_demo(tmp_path / "b")
    first = (tmp_path / "a" / "index.html").read_bytes()
    assert first == (tmp_path / "b" / "index.html").read_bytes()
