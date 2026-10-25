"""cost_summary: the Duo cost log table summarised by what ran."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import cost_summary

HEADER = (
    "| Date and time (GMT-3) | What ran | Session URL | Merge request | Credits before "
    "| Credits after | Delta | Pipelines | Job minutes | Job seconds | Retries | Notes |"
)
SEPARATOR = "|---|---|---|---|---|---|---|---|---|---|---|---|"


def row(
    what: str,
    delta: str = "human",
    pipelines: str = "1",
    minutes: str = "2",
    seconds: str = "79.5",
    retries: str = "0",
    notes: str = "",
) -> str:
    cells = ["2026-10-25 10:00", what, "", "", "human", "human", delta]
    cells += [pipelines, minutes, seconds, retries, notes]
    return "| " + " | ".join(cells) + " |"


def table(*rows: str) -> str:
    return "\n".join(["Intro text.", "", HEADER, SEPARATOR, *rows, "", "Trailing text."])


def test_groups_rows_by_what_ran_and_sums_every_column() -> None:
    text = table(
        row("Developer Flow", delta="1.5", pipelines="2", minutes="3", seconds="10", retries="1"),
        row("Developer Flow", delta="0.25", pipelines="1", minutes="4", seconds="0.5", retries="0"),
        row("Fix CI/CD", delta="2", pipelines="1", minutes="1", seconds="5", retries="2"),
    )
    result = cost_summary.summarize(text)
    assert list(result["groups"]) == ["Developer Flow", "Fix CI/CD"]
    dev = result["groups"]["Developer Flow"]
    assert dev == {
        "runs": 2,
        "pipelines": 3,
        "job_minutes": 7,
        "job_seconds": 10.5,
        "retries": 1,
        "credits": 1.75,
        "missing": {
            "pipelines": 0,
            "job_minutes": 0,
            "job_seconds": 0,
            "retries": 0,
            "credits": 0,
        },
    }
    assert result["total"]["runs"] == 3
    assert result["total"]["credits"] == 3.75
    assert result["total"]["job_seconds"] == 15.5
    assert result["total"]["retries"] == 3


def test_decimal_sums_are_exact() -> None:
    text = table(row("A", seconds="0.1"), row("A", seconds="0.2"))
    assert cost_summary.summarize(text)["groups"]["A"]["job_seconds"] == 0.3


def test_what_ran_is_stripped() -> None:
    text = table(row("  Flow  "), row("Flow"))
    assert list(cost_summary.summarize(text)["groups"]) == ["Flow"]


def test_unknown_cells_add_nothing_and_are_counted_as_missing() -> None:
    text = table(
        row("A", delta="human", pipelines="null", minutes="", seconds="n/a", retries="null"),
        row("A", delta="1", pipelines="2", minutes="3", seconds="4", retries="5"),
    )
    stats = cost_summary.summarize(text)["groups"]["A"]
    assert stats["runs"] == 2
    assert (stats["pipelines"], stats["job_minutes"], stats["job_seconds"]) == (2, 3, 4)
    assert (stats["retries"], stats["credits"]) == (5, 1)
    assert stats["missing"] == {
        "pipelines": 1,
        "job_minutes": 1,
        "job_seconds": 1,
        "retries": 1,
        "credits": 1,
    }


def test_group_with_only_unknown_cells_sums_to_zero() -> None:
    text = table(row("A", "human", "null", "null", "null", "null"))
    stats = cost_summary.summarize(text)["groups"]["A"]
    assert stats["runs"] == 1
    assert stats["credits"] == 0
    assert stats["pipelines"] == stats["job_minutes"] == stats["job_seconds"] == 0
    assert stats["retries"] == 0
    assert stats["missing"] == dict.fromkeys(
        ["pipelines", "job_minutes", "job_seconds", "retries", "credits"], 1
    )


def test_total_adds_the_missing_counts_of_all_groups() -> None:
    text = table(row("A", delta="human"), row("B", delta="null"), row("B", delta="1"))
    total = cost_summary.summarize(text)["total"]
    assert total["missing"]["credits"] == 2
    assert total["credits"] == 1


@pytest.mark.parametrize("cell", ["1e3", "nan", "inf", "1_0", "0x10", "1,5", "--1", "."])
def test_only_integers_and_decimals_are_numeric(cell: str) -> None:
    stats = cost_summary.summarize(table(row("A", delta=cell)))["groups"]["A"]
    assert stats["credits"] == 0
    assert stats["missing"]["credits"] == 1


@pytest.mark.parametrize("cell,value", [(" 7 ", 7), ("-1.5", -1.5), ("+2", 2), ("0.30", 0.3)])
def test_numeric_cells_are_stripped_and_signed(cell: str, value: float) -> None:
    stats = cost_summary.summarize(table(row("A", delta=cell)))["groups"]["A"]
    assert stats["credits"] == value
    assert stats["missing"]["credits"] == 0


def test_a_link_in_the_pipelines_cell_is_unknown() -> None:
    link = "[2985662569](https://gitlab.com/g/p/-/pipelines/2985662569)"
    stats = cost_summary.summarize(table(row("A", pipelines=link)))["groups"]["A"]
    assert stats["pipelines"] == 0
    assert stats["missing"]["pipelines"] == 1


def test_table_without_data_rows() -> None:
    result = cost_summary.summarize(table())
    assert result["groups"] == {}
    assert result["total"]["runs"] == 0
    assert result["total"]["credits"] == 0
    assert result["total"]["missing"]["credits"] == 0


def test_header_as_last_line_without_separator() -> None:
    assert cost_summary.summarize(HEADER)["groups"] == {}


def test_text_after_the_table_is_ignored() -> None:
    text = table(row("A")) + "\n| not | a | row |\n" + row("B")
    assert list(cost_summary.summarize(text)["groups"]) == ["A"]


def test_short_rows_count_absent_cells_as_missing() -> None:
    text = "\n".join([HEADER, SEPARATOR, "| 2026-10-25 | A |"])
    stats = cost_summary.summarize(text)["groups"]["A"]
    assert stats["runs"] == 1
    assert stats["missing"]["credits"] == 1
    assert stats["missing"]["retries"] == 1


def test_escaped_pipe_in_a_cell_does_not_shift_the_columns() -> None:
    text = table(row("A", delta="3", notes=r"a \| b"), row("A\\|B", delta="1"))
    groups = cost_summary.summarize(text)["groups"]
    assert groups["A"]["credits"] == 3
    assert groups["A\\|B"]["credits"] == 1


def test_missing_header_raises_value_error_naming_the_table() -> None:
    with pytest.raises(ValueError, match="table"):
        cost_summary.summarize("| a | b |\n|---|---|\n| 1 | 2 |\n")


def test_header_must_be_exact() -> None:
    with pytest.raises(ValueError, match="table"):
        cost_summary.summarize(HEADER.replace("Delta", "Change") + "\n" + SEPARATOR)


def test_cli_prints_a_markdown_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "log.md"
    path.write_text(table(row("A", delta="1"), row("B")), encoding="utf-8")
    assert cost_summary.main([str(path)]) == 0
    captured = capsys.readouterr()
    lines = captured.out.strip().splitlines()
    assert lines[0] == (
        "| What ran | Runs | Pipelines | Job minutes | Job seconds | Retries | Credits | Missing |"
    )
    assert lines[1] == "|---|---|---|---|---|---|---|---|"
    assert lines[2].startswith("| A | 1 | 1 | 2 | 79.5 | 0 | 1 | 0 |")
    assert lines[3].startswith("| B | 1 |")
    assert lines[4].startswith("| Total | 2 | 2 | 4 | 159 | 0 | 1 | 1 |")
    assert len(lines) == 5
    assert captured.err == ""


def test_cli_json_prints_the_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "log.md"
    text = table(row("A", delta="1"))
    path.write_text(text, encoding="utf-8")
    assert cost_summary.main([str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == cost_summary.summarize(text)


def test_cli_missing_file_exits_2_with_stderr_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cost_summary.main([str(tmp_path / "absent.md")]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "absent.md" in captured.err


@pytest.mark.parametrize("flags", [[], ["--json"]])
def test_cli_file_without_table_exits_2_with_stderr_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], flags: list[str]
) -> None:
    path = tmp_path / "log.md"
    path.write_text("no table here\n", encoding="utf-8")
    assert cost_summary.main([str(path), *flags]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "table" in captured.err


def test_cli_empty_table_exits_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "log.md"
    path.write_text(table(), encoding="utf-8")
    assert cost_summary.main([str(path)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 3
    assert lines[2].startswith("| Total | 0 |")


def test_cli_reads_the_real_cost_log(capsys: pytest.CaptureFixture[str]) -> None:
    repo = Path(__file__).resolve().parents[2]
    assert cost_summary.main([str(repo / "docs/submission/cost-log.md"), "--json"]) == 0
    assert "groups" in json.loads(capsys.readouterr().out)
