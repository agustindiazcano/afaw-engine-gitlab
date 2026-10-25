#!/usr/bin/env python3
"""Build the benchmark tables of docs/experiments.md from the merge request and pipeline lists.

``lead_times`` and ``pipeline_stats`` are pure functions of the lists they receive and ``render``
writes the two markdown tables. The command line reads two JSON files and prints the tables to
stdout; it writes no file.

Usage:
    python -m scripts.benchmark_report --merge-requests FILE --pipelines FILE
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

NOT_AVAILABLE = "n/a"
MR_HEADER = "| MR | Lead time (minutes) |"
PIPELINE_HEADER = (
    "| Pipelines | Success | Failed | Other | Success rate (%) | Median duration (minutes) |"
)


def _parse(stamp: str) -> datetime:
    """An ISO 8601 timestamp as an aware datetime; one without an offset is read as UTC."""
    moment = datetime.fromisoformat(stamp)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _minutes(start: str, end: str) -> float:
    """The minutes from the ``start`` timestamp to the ``end`` timestamp, unrounded."""
    return (_parse(end) - _parse(start)).total_seconds() / 60


def lead_times(merge_requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The lead time in minutes of every merged request, sorted by iid; unmerged are ignored."""
    merged = [item for item in merge_requests if item.get("merged_at") is not None]
    rows = [
        {"iid": item["iid"], "minutes": round(_minutes(item["created_at"], item["merged_at"]), 1)}
        for item in merged
    ]
    return sorted(rows, key=lambda row: row["iid"])


def pipeline_stats(pipelines: list[dict[str, Any]]) -> dict[str, Any]:
    """The pipeline counts, the success rate and the median duration, as one dict."""
    success = sum(1 for item in pipelines if item.get("status") == "success")
    failed = sum(1 for item in pipelines if item.get("status") == "failed")
    durations = [
        _minutes(item["created_at"], item["finished_at"])
        for item in pipelines
        if item.get("status") in ("success", "failed") and item.get("finished_at") is not None
    ]
    finished = success + failed
    return {
        "total": len(pipelines),
        "success": success,
        "failed": failed,
        "other": len(pipelines) - finished,
        "success_rate": round(100 * success / finished, 1) if finished else None,
        "median_minutes": round(statistics.median(durations), 1) if durations else None,
    }


def _cell(value: object) -> str:
    """A table cell: ``n/a`` for None, else the value as text."""
    return NOT_AVAILABLE if value is None else str(value)


def render(lead: list[dict[str, Any]], stats: dict[str, Any]) -> str:
    """The lead time table, a blank line and the pipeline table, as markdown."""
    lines = [MR_HEADER, "|---|---|"]
    lines += [f"| !{item['iid']} | {item['minutes']} |" for item in lead]
    lines += ["", PIPELINE_HEADER, "|---|---|---|---|---|---|"]
    cells = [stats[key] for key in ("total", "success", "failed", "other")]
    cells += [stats["success_rate"], stats["median_minutes"]]
    lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    return "\n".join(lines)


def _load_list(path: Path) -> list[dict[str, Any]]:
    """The JSON list held by the file; raises ValueError or OSError when it cannot be read."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("expected a JSON list")
    return data


def main(argv: list[str] | None = None) -> int:
    """Print the benchmark tables; exit 2 with a message on stderr when a file is unusable."""
    parser = argparse.ArgumentParser(prog="benchmark_report", description=__doc__)
    parser.add_argument("--merge-requests", type=Path, required=True)
    parser.add_argument("--pipelines", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        merge_requests = _load_list(args.merge_requests)
    except (OSError, ValueError) as error:
        sys.stderr.write(f"benchmark_report: {args.merge_requests}: {error}\n")
        return 2
    try:
        pipelines = _load_list(args.pipelines)
    except (OSError, ValueError) as error:
        sys.stderr.write(f"benchmark_report: {args.pipelines}: {error}\n")
        return 2
    sys.stdout.write(render(lead_times(merge_requests), pipeline_stats(pipelines)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
