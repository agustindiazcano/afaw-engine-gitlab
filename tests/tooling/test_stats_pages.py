"""The experiments and environment pages: measured data, charts as SVG, a table for every chart."""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Any

import pytest

from scripts.afaw_state import stats_pages
from scripts.afaw_state.source import read_experiments

DATA_PATH = Path(__file__).resolve().parents[2] / "docs" / "data" / "experiments.json"


@pytest.fixture(scope="module")
def data() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return loaded


@pytest.fixture(scope="module")
def experiments(data: dict[str, Any]) -> str:
    return stats_pages.experiments_page(data)


@pytest.fixture(scope="module")
def environment(data: dict[str, Any]) -> str:
    return stats_pages.environment_page(data)


# ---- the data file


def test_every_section_of_the_data_names_its_source(data: dict[str, Any]) -> None:
    for section in ("coverage", "mutation", "minutes", "environment"):
        assert data[section]["source"].strip(), section


def test_percentages_are_between_zero_and_one_hundred(data: dict[str, Any]) -> None:
    for section in ("coverage", "mutation"):
        for row in data[section]["rows"]:
            assert 0 <= row["before"] <= 100 and 0 <= row["after"] <= 100, row


def test_a_mutation_score_is_its_killed_over_its_total(data: dict[str, Any]) -> None:
    for row in data["mutation"]["rows"]:
        assert round(100 * row["killed_before"] / row["total_before"], 1) == row["before"]
        assert round(100 * row["killed_after"] / row["total_after"], 1) == row["after"]


def test_hidden_tests_passed_never_exceed_the_total(data: dict[str, Any]) -> None:
    for tool in data["hard_builds"]:
        assert 0 <= tool["hidden_passed"] <= tool["hidden_total"]


# ---- the bar chart


def test_bar_widths_are_proportional_to_the_values() -> None:
    svg = stats_pages.bars([("a", [50.0]), ("b", [100.0])], ["Value"], "percent", 100.0)
    widths = [float(w) for w in re.findall(r'<rect class="bar s1" [^>]*width="([0-9.]+)"', svg)]
    assert len(widths) == 2 and widths[1] == pytest.approx(2 * widths[0], rel=0.02)


def test_a_chart_with_two_series_has_a_legend_and_direct_labels() -> None:
    html = stats_pages.chart(
        "Coverage", [("a", [10.0, 20.0])], ["Before", "After"], "percent", 100.0
    )
    assert 'class="legend"' in html and "Before" in html and "After" in html
    assert ">10<" in html and ">20<" in html  # the values are written next to the bars


def test_a_chart_with_one_series_has_no_legend() -> None:
    html = stats_pages.chart("Minutes", [("a", [12.1])], ["Minutes"], "minutes", None)
    assert 'class="legend"' not in html


def test_every_chart_is_labelled_and_has_a_table_view() -> None:
    html = stats_pages.chart(
        "Coverage", [("a", [10.0, 20.0])], ["Before", "After"], "percent", 100.0
    )
    assert 'role="img"' in html and 'aria-label="Coverage' in html
    assert "<details" in html and "<table" in html


def test_labels_are_escaped() -> None:
    html = stats_pages.chart("T", [("<b>x</b>", [1.0])], ["S"], "u", None)
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html


def test_a_zero_value_draws_no_bar_but_is_still_labelled() -> None:
    svg = stats_pages.bars([("a", [0.0])], ["V"], "percent", 100.0)
    assert ">0<" in svg


# ---- the experiments page


def test_the_experiments_page_has_the_project_name_nav_and_author_footer(experiments: str) -> None:
    assert "<title>AFAW Engine Gitlab" in experiments
    assert "<nav" in experiments and "<footer" in experiments
    assert 'href="https://www.agustindiazcano.com/"' in experiments


def test_the_experiments_page_shows_the_headline_numbers(experiments: str) -> None:
    assert "39 of 39" in experiments  # hidden acceptance tests passed
    assert "6 of 6" in experiments  # planted defects repaired
    assert "363.45 of 500" in experiments  # credits, read by the human


def test_the_experiments_page_has_the_three_charts_and_the_merge_table(experiments: str) -> None:
    assert experiments.count('role="img"') >= 3
    for label in ("Coverage", "Mutation score", "Minutes"):
        assert label in experiments
    assert "!35" in experiments and "!16" in experiments


def test_the_experiments_page_names_every_source(experiments: str, data: dict[str, Any]) -> None:
    for section in ("coverage", "mutation", "minutes"):
        assert data[section]["source"].split(",")[0][:25] in experiments


def test_the_experiments_page_has_no_script_and_no_remote_resource(experiments: str) -> None:
    assert "<script" not in experiments
    assert "http://" not in experiments and "src=" not in experiments


def test_every_chaos_row_says_what_was_expected_and_what_was_seen(data: dict[str, Any]) -> None:
    assert data["chaos"]
    for row in data["chaos"]:
        assert all(row[k] for k in ("id", "fault", "expected", "observed"))
        assert isinstance(row["held"], bool)


def test_the_experiments_page_lists_the_chaos_and_security_results(experiments: str) -> None:
    assert "Chaos and security" in experiments
    for ident in ("C1", "C3", "S1"):
        assert f"<td>{ident}</td>" in experiments
    assert "Held" in experiments


def test_the_chaos_table_shows_failures_as_failures() -> None:
    rows = [
        {"id": "X1", "fault": "f", "expected": "e", "observed": "o", "held": False},
        {"id": "X2", "fault": "f", "expected": "e", "observed": "o", "held": True},
    ]
    html = stats_pages.chaos_table(rows)
    assert "Did not hold" in html and "Held" in html
    assert html.index("X1") < html.index("Did not hold") < html.index("X2")


# ---- the environment page


def test_the_environment_page_computes_the_sci_with_the_tool_and_shows_the_assumptions(
    environment: str,
) -> None:
    assert "0.272" in environment and "0.049" in environment  # gCO2e per run at 579 g per kWh
    assert "0.161" in environment and "0.029" in environment  # at 343 g per kWh
    for assumption in ("0.71", "4.26", "1.1", "579", "343"):
        assert assumption in environment


def test_the_environment_page_states_the_ratio_and_the_limits(environment: str) -> None:
    assert "5.5 times" in environment  # 309 s over 56 s
    assert "SCI without M" in environment
    assert "not measured on the runner" in environment.replace("\n", " ")


def test_the_environment_page_has_charts_with_table_views(environment: str) -> None:
    assert environment.count('role="img"') >= 2 and environment.count("<details") >= 2


def test_the_environment_page_claims_no_saving_beyond_the_measured_comparison(
    environment: str,
) -> None:
    assert "tonnes" not in environment and "trees" not in environment


# ---- reading the data and building the outputs


def test_reading_the_data_from_a_ref_returns_none_when_the_file_is_absent() -> None:
    def run(args: list[str]) -> str:
        if args[0] == "ls-tree":
            return ""
        raise AssertionError(args)

    assert read_experiments(run, "origin/main") is None


def test_reading_the_data_from_a_ref_parses_the_json() -> None:
    def run(args: list[str]) -> str:
        if args[0] == "ls-tree":
            return "docs/data/experiments.json\n"
        return '{"as_of": "2026-10-25"}'

    assert read_experiments(run, "origin/main") == {"as_of": "2026-10-25"}


def test_the_extra_outputs_are_the_two_pages(data: dict[str, Any]) -> None:
    out = stats_pages.extra_outputs(data)
    assert sorted(out) == ["environment.html", "experiments.html"]
    assert stats_pages.extra_outputs(None) == {}


def test_the_nav_links_to_both_pages() -> None:
    from scripts.afaw_state import brand

    nav = brand.nav()
    assert 'href="/experiments/"' in nav and 'href="/environment/"' in nav


# ------------------------------------------------------------------ the hands-off panel


def test_the_experiments_page_has_the_hands_off_loop_section(experiments: str) -> None:
    assert "Hands-off loop" in experiments


def test_every_stage_is_listed_with_its_merge_request(
    experiments: str, data: dict[str, Any]
) -> None:
    stages = data["handoff"]["stages"]
    assert [s["stage"] for s in stages] == [
        "plan", "create", "verify", "secure", "package", "release", "configure", "monitor",
        "govern",
    ]
    for stage in stages:
        assert f"!{stage['mr']}" in experiments and f"#{stage['issue']}" in experiments


def test_the_autonomy_numbers_come_from_the_data_file(
    experiments: str, data: dict[str, Any]
) -> None:
    a = data["handoff"]["autonomy"]
    assert f"{a['agent_only']} of {a['merge_requests']}" in experiments
    assert str(a["median_minutes"]) in experiments


def test_the_repair_chain_is_listed_link_by_link(experiments: str, data: dict[str, Any]) -> None:
    chain = data["handoff"]["chain"]
    assert len(chain) >= 6
    for link in chain:
        assert link["link"] in experiments and link["utc"] in experiments


def test_the_page_says_what_the_evidence_does_not_prove(
    experiments: str, data: dict[str, Any]
) -> None:
    limits = data["handoff"]["limits"]
    assert any("token" in text for text in limits)
    for text in limits:
        assert escape(text) in experiments


def test_the_guard_merge_tile_and_the_autonomy_panel_give_the_same_number(
    experiments: str, data: dict[str, Any]
) -> None:
    count = data["handoff"]["autonomy"]["guard_merged"]
    assert f"<b>{count}</b><span>Merges by merge_guard" in experiments


def test_the_end_to_end_rehearsal_is_listed_link_by_link(
    experiments: str, data: dict[str, Any]
) -> None:
    rehearsal = data["handoff"]["rehearsal"]
    assert len(rehearsal["links"]) >= 8
    for link in rehearsal["links"]:
        assert escape(link["link"]) in experiments and link["utc"] in experiments
    assert str(rehearsal["credits_used"]) in experiments
    assert "gCO2eq" in experiments


def test_the_long_chain_lists_every_task_with_its_issue_and_merge_request(
    experiments: str, data: dict[str, Any]
) -> None:
    chain = data["handoff"]["long_chain"]
    assert len(chain["tasks"]) == 3
    for task in chain["tasks"]:
        assert f"#{task['issue']}" in experiments and f"!{task['mr']}" in experiments
        assert task["task"] in experiments
    assert chain["total"] in experiments
    assert "gCO2eq" in experiments
