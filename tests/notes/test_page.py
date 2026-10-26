"""Structure of the notes page: responsive, accessible, light and dark, small."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from notes_app import app as app_module
from notes_app.app import create_app

STATIC_PAGE = Path(__file__).resolve().parents[2] / "src" / "notes_app" / "static" / "index.html"
MAX_PAGE_BYTES = 20_000


@pytest.fixture()
def html() -> str:
    return TestClient(create_app()).get("/").text


def test_the_page_is_served_from_the_static_file(html: str) -> None:
    assert STATIC_PAGE.is_file()
    assert html == STATIC_PAGE.read_text(encoding="utf-8")


def test_the_page_is_read_once_at_app_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = tmp_path / "index.html"
    page.write_text("<html>AFAW demo notes /api/notes</html>", encoding="utf-8")
    monkeypatch.setattr(app_module, "STATIC_PAGE", page)
    client = TestClient(create_app())
    page.write_text("<html>changed</html>", encoding="utf-8")
    assert "AFAW demo notes" in client.get("/").text


@pytest.mark.characterization(reason="budget guard: the old page was already small")
def test_the_page_stays_under_the_weight_budget(html: str) -> None:
    assert len(html.encode("utf-8")) < MAX_PAGE_BYTES


@pytest.mark.characterization(reason="guard: the old page already had both")
def test_the_page_declares_language_and_viewport(html: str) -> None:
    assert '<html lang="en"' in html
    assert re.search(r'<meta name="viewport" content="width=device-width', html)


def test_the_input_has_a_real_label(html: str) -> None:
    assert re.search(r'<label[^>]+for="t"', html)
    assert 'id="t"' in html


def test_the_page_has_one_button_and_the_required_ids(html: str) -> None:
    assert len(re.findall(r"<button\b", html)) == 1
    for ident in ("t", "f", "n", "v", "count", "empty"):
        assert f'id="{ident}"' in html
    assert re.search(r'<ul[^>]+id="n"', html)


def test_the_page_supports_dark_mode_and_reduced_motion(html: str) -> None:
    assert "prefers-color-scheme: dark" in html
    assert "prefers-reduced-motion" in html
    assert ":focus-visible" in html


def test_the_spacing_scale_and_colours_are_css_variables(html: str) -> None:
    for step in (4, 8, 12, 16, 24, 32):
        assert re.search(rf"--space-{step}:\s*{step}px", html)
    assert "--primary:" in html
    assert "#0b5fff" in html


def test_the_counter_is_live_and_errors_are_alerts(html: str) -> None:
    assert re.search(r'id="count"[^>]*aria-live="polite"', html)
    assert 'role="alert"' in html
    assert "No notes yet. Add the first one." in html


def test_the_page_has_a_logo_and_the_subtitle(html: str) -> None:
    assert "<svg" in html
    assert "changed by AFAW agents" in html


@pytest.mark.characterization(reason="guard: the old page already loaded nothing external")
def test_the_page_loads_nothing_from_outside(html: str) -> None:
    assert not re.search(r"(src|href)=\"https?://", html)
    assert "@import" not in html
    assert "<img" not in html


def test_the_page_has_a_summary_line_a_clear_control_and_a_hint(html: str) -> None:
    assert 'id="stats"' in html
    assert re.search(r'id="clear"[^>]*role="button"', html)
    assert 'class="hint"' in html


def test_the_summary_is_read_from_the_stats_endpoint(html: str) -> None:
    assert "(d.length+1)" not in html
    assert "fetch('/api/stats')" in html
    assert re.search(r"\$\('stats'\)\.textContent=", html)
    assert "d.length+' notes'" not in html


def test_the_summary_shows_the_count_and_the_longest_length(html: str) -> None:
    assert "' notes, longest '" in html
    assert "' characters'" in html
    assert "'0 notes'" in html


def test_the_summary_is_refreshed_after_every_add_and_delete(html: str) -> None:
    # Adding, deleting and clearing all end with load(), and load() reads the stats.
    load = re.search(r"async function load\(\)\{.*?\n(?=async function removeNote)", html, re.S)
    assert load is not None
    assert "fetch('/api/stats')" in load.group(0)
    assert html.count("await load()") >= 3


def test_the_clear_control_deletes_the_notes_on_the_server(html: str) -> None:
    bound = re.search(r"\$\('clear'\)\.addEventListener\('click',(\w+|\(\)=>\{\})\)", html)
    assert bound is not None
    assert bound.group(1) != "()=>{}"
    assert re.search(r"fetch\('/api/notes',\{method:'DELETE'\}\)", html)


def test_the_hint_text_colour_differs_from_the_card_background(html: str) -> None:
    hint = re.search(r"\.hint\{[^}]*\}", html)
    assert hint is not None
    colour = re.search(r"(?<![-\w])color:([^;}]+)", hint.group(0))
    assert colour is not None
    assert colour.group(1).strip() != "var(--surface)"


def test_each_note_has_a_delete_control_that_is_not_a_button(html: str) -> None:
    # The browser tests select the page's single <button>, so the control must be another element.
    assert "createElement('span')" in html
    assert "method:'DELETE'" in html
    assert "/api/notes/" in html
    assert html.count("<button") == 1
    assert "createElement('button')" not in html


COMMIT_URL = (
    "https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/commit/"
)


def test_the_footer_links_the_commit_to_its_gitlab_page(html: str) -> None:
    assert COMMIT_URL in html
    assert "createElement('a')" in html
    assert re.search(r"\.href=COMMIT_URL\+v\.commit_sha", html)


def test_the_commit_link_opens_in_the_same_tab_with_noopener(html: str) -> None:
    assert re.search(r"\.rel='noopener'", html)
    assert "target" not in html.replace("targetless", "")


def test_the_commit_text_stays_plain_when_the_version_is_unknown(html: str) -> None:
    assert re.search(r"v\.commit_sha(\s*)!==(\s*)'unknown'", html)
