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


def test_the_summary_shows_the_number_of_notes_without_an_offset(html: str) -> None:
    assert "(d.length+1)" not in html
    assert re.search(r"\$\('stats'\)\.textContent=d\.length\+' notes'", html)


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
