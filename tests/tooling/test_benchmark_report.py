"""benchmark_report: benchmark tables from the merge request and pipeline lists."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import benchmark_report


def mr(iid: int, created: str, merged: str | None) -> dict[str, object]:
    return {"iid": iid, "created_at": created, "merged_at": merged}


def pipe(status: str, created: str, finished: str | None) -> dict[str, object]:
    return {"status": status, "created_at": created, "finished_at": finished}


def test_lead_times_sorted_rounded_and_skips_unmerged() -> None:
    items = [
        mr(9, "2026-10-25T10:00:00Z", "2026-10-25T10:30:00Z"),
        mr(3, "2026-10-25T10:00:00.000Z", "2026-10-25T10:01:30.5Z"),
        mr(5, "2026-10-25T10:00:00Z", None),
    ]
    assert benchmark_report.lead_times(items) == [
        {"iid": 3, "minutes": 1.5},
        {"iid": 9, "minutes": 30.0},
    ]


def test_lead_times_mixed_offsets() -> None:
    items = [mr(1, "2026-10-25T07:00:00-03:00", "2026-10-25T10:45:00+00:00")]
    assert benchmark_report.lead_times(items) == [{"iid": 1, "minutes": 45.0}]


def test_lead_times_rounds_to_one_decimal() -> None:
    items = [mr(1, "2026-10-25T10:00:00Z", "2026-10-25T10:01:00.3+00:00")]
    assert benchmark_report.lead_times(items) == [{"iid": 1, "minutes": 1.0}]


def test_lead_times_empty() -> None:
    assert benchmark_report.lead_times([]) == []


def test_pipeline_stats_counts_rate_and_odd_median() -> None:
    items = [
        pipe("success", "2026-10-25T10:00:00Z", "2026-10-25T10:02:00Z"),
        pipe("failed", "2026-10-25T10:00:00Z", "2026-10-25T10:10:00Z"),
        pipe("success", "2026-10-25T10:00:00Z", "2026-10-25T10:04:00Z"),
        pipe("canceled", "2026-10-25T10:00:00Z", "2026-10-25T10:50:00Z"),
        pipe("running", "2026-10-25T10:00:00Z", None),
    ]
    assert benchmark_report.pipeline_stats(items) == {
        "total": 5,
        "success": 2,
        "failed": 1,
        "other": 2,
        "success_rate": 66.7,
        "median_minutes": 4.0,
    }


def test_pipeline_stats_even_median_is_mean_of_middle_values() -> None:
    items = [
        pipe("success", "2026-10-25T10:00:00Z", "2026-10-25T10:01:00Z"),
        pipe("success", "2026-10-25T10:00:00Z", "2026-10-25T10:02:00Z"),
        pipe("failed", "2026-10-25T10:00:00Z", "2026-10-25T10:04:00Z"),
        pipe("failed", "2026-10-25T10:00:00Z", "2026-10-25T10:09:00Z"),
    ]
    stats = benchmark_report.pipeline_stats(items)
    assert stats["median_minutes"] == 3.0
    assert stats["success_rate"] == 50.0


def test_pipeline_stats_ignores_unfinished_in_median_only() -> None:
    items = [
        pipe("success", "2026-10-25T10:00:00Z", None),
        pipe("failed", "2026-10-25T10:00:00Z", "2026-10-25T10:06:00Z"),
    ]
    stats = benchmark_report.pipeline_stats(items)
    assert stats["median_minutes"] == 6.0
    assert stats["success"] == 1


def test_pipeline_stats_none_values() -> None:
    assert benchmark_report.pipeline_stats([]) == {
        "total": 0,
        "success": 0,
        "failed": 0,
        "other": 0,
        "success_rate": None,
        "median_minutes": None,
    }
    only_other = benchmark_report.pipeline_stats(
        [pipe("canceled", "2026-10-25T10:00:00Z", "2026-10-25T10:05:00Z")]
    )
    assert only_other["success_rate"] is None
    assert only_other["median_minutes"] is None
    assert only_other["other"] == 1


def test_render_tables() -> None:
    lead = [{"iid": 3, "minutes": 1.5}, {"iid": 9, "minutes": 30.0}]
    stats = {
        "total": 5,
        "success": 2,
        "failed": 1,
        "other": 2,
        "success_rate": 66.7,
        "median_minutes": None,
    }
    assert benchmark_report.render(lead, stats).splitlines() == [
        "| MR | Lead time (minutes) |",
        "|---|---|",
        "| !3 | 1.5 |",
        "| !9 | 30.0 |",
        "",
        "| Pipelines | Success | Failed | Other | Success rate (%) | Median duration (minutes) |",
        "|---|---|---|---|---|---|",
        "| 5 | 2 | 1 | 2 | 66.7 | n/a |",
    ]


def test_render_without_merge_requests() -> None:
    stats = benchmark_report.pipeline_stats([])
    lines = benchmark_report.render([], stats).splitlines()
    assert lines[:3] == ["| MR | Lead time (minutes) |", "|---|---|", ""]
    assert lines[-1] == "| 0 | 0 | 0 | 0 | n/a | n/a |"


def write(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_main_prints_render(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    merge_requests = write(
        tmp_path / "mrs.json", [mr(2, "2026-10-25T10:00:00Z", "2026-10-25T10:20:00Z")]
    )
    pipelines = write(
        tmp_path / "pipes.json", [pipe("success", "2026-10-25T10:00:00Z", "2026-10-25T10:03:00Z")]
    )
    code = benchmark_report.main(
        ["--merge-requests", str(merge_requests), "--pipelines", str(pipelines)]
    )
    out = capsys.readouterr()
    expected = benchmark_report.render(
        [{"iid": 2, "minutes": 20.0}],
        benchmark_report.pipeline_stats(json.loads(pipelines.read_text())),
    )
    assert code == 0
    assert out.out == expected + "\n"
    assert out.err == ""


def test_main_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pipelines = write(tmp_path / "pipes.json", [])
    code = benchmark_report.main(
        ["--merge-requests", str(tmp_path / "nope.json"), "--pipelines", str(pipelines)]
    )
    out = capsys.readouterr()
    assert code == 2
    assert out.out == ""
    assert "nope.json" in out.err


def test_main_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    merge_requests = write(tmp_path / "mrs.json", [])
    bad = tmp_path / "pipes.json"
    bad.write_text("{not json", encoding="utf-8")
    code = benchmark_report.main(["--merge-requests", str(merge_requests), "--pipelines", str(bad)])
    out = capsys.readouterr()
    assert code == 2
    assert out.out == ""
    assert "pipes.json" in out.err


def test_main_rejects_non_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    merge_requests = write(tmp_path / "mrs.json", {"iid": 1})
    pipelines = write(tmp_path / "pipes.json", [])
    code = benchmark_report.main(
        ["--merge-requests", str(merge_requests), "--pipelines", str(pipelines)]
    )
    out = capsys.readouterr()
    assert code == 2
    assert out.out == ""
    assert "mrs.json" in out.err
