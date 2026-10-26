"""The ecological indicator at the top of the dashboard: measured range and assumptions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_state
from scripts.afaw_state.eco import indicator, inject

SCI = {
    "flows": 12,
    "job_seconds": 37004.0,
    "gco2eq_low": 5.507,
    "gco2eq_mid": 20.1,
    "gco2eq_high": 55.778,
    "assumptions": "SCI without M; Duo model energy not measured",
}
PAGE = '<main><h1>Project status</h1><p class="meta">x</p></main>'


def test_the_indicator_shows_the_per_flow_range_and_the_count() -> None:
    html = indicator(SCI)
    assert "0.46 to 4.65" in html  # 5.507 / 12 and 55.778 / 12
    assert "12 merged merge requests" in html
    assert "37004" in html


def test_the_indicator_says_what_it_leaves_out() -> None:
    html = indicator(SCI)
    assert "SCI without M" in html
    assert "Duo" in html and "not measured" in html


def test_without_flows_it_says_nothing_was_measured() -> None:
    html = indicator({**SCI, "flows": 0, "job_seconds": 0, "gco2eq_low": 0, "gco2eq_high": 0})
    assert "No flow measured" in html
    assert "to" not in html.split("No flow measured")[0][-20:]


def test_the_indicator_goes_right_after_the_title() -> None:
    out = inject(PAGE, SCI)
    assert out.index("<h1>") < out.index('class="banner eco"') < out.index('class="meta"')


def test_a_page_without_a_title_is_left_alone() -> None:
    assert inject("<main></main>", SCI) == "<main></main>"


def test_text_from_the_data_is_escaped() -> None:
    html = indicator({**SCI, "assumptions": "<script>x</script>"})
    assert "<script>" not in html


def test_build_state_adds_the_indicator_when_given_the_sci_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sci = tmp_path / "sci.json"
    sci.write_text(json.dumps(SCI), encoding="utf-8")
    out = tmp_path / "out"
    assert build_state.main(["--ref", "HEAD", "--out", str(out), "--sci", str(sci)]) == 0
    assert 'class="banner eco"' in (out / "dashboard.html").read_text(encoding="utf-8")
