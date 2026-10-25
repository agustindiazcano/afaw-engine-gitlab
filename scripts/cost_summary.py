#!/usr/bin/env python3
"""Summarise docs/submission/cost-log.md by what ran, for the tables of docs/experiments.md.

Reads the table with one row per Duo run, groups the data rows by the "What ran" cell and sums
the credits (the "Delta" cells), pipelines, job minutes, job seconds and retries. A cell that is
not a number (``human``, ``null``, empty) adds nothing to a sum and is counted as missing, never
as zero. It only reads the file it is given and writes to stdout.

Usage:
    python -m scripts.cost_summary docs/submission/cost-log.md [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

HEADER = (
    "| Date and time (GMT-3) | What ran | Session URL | Merge request | Credits before "
    "| Credits after | Delta | Pipelines | Job minutes | Job seconds | Retries | Notes |"
)
COLUMNS = [cell.strip() for cell in HEADER.strip("|").split("|")]
WHAT_RAN = COLUMNS.index("What ran")
# Stat name -> the table column whose cells it sums.
SUMMED = {
    "pipelines": "Pipelines",
    "job_minutes": "Job minutes",
    "job_seconds": "Job seconds",
    "retries": "Retries",
    "credits": "Delta",
}
NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)", re.ASCII)
CELL_SPLIT = re.compile(r"(?<!\\)\|")
TABLE_COLUMNS = ["What ran", "Runs", "Pipelines", "Job minutes", "Job seconds", "Retries"]
TABLE_COLUMNS += ["Credits", "Missing"]


def _cells(line: str) -> list[str]:
    """The stripped cells of a markdown table row; ``\\|`` does not split a cell."""
    body = line.strip()[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [cell.strip() for cell in CELL_SPLIT.split(body)]


def _number(cell: str) -> Decimal | None:
    """The cell as a number, or None when it is not an integer or a decimal."""
    text = cell.strip()
    return Decimal(text) if NUMBER.fullmatch(text) else None


def _plain(value: Decimal) -> int | float:
    """An int for a whole value, else a float."""
    return int(value) if value == value.to_integral_value() else float(value)


def _empty_stats() -> dict[str, Any]:
    stats: dict[str, Any] = {"runs": 0}
    stats.update({name: Decimal(0) for name in SUMMED})
    stats["missing"] = dict.fromkeys(SUMMED, 0)
    return stats


def _add_row(stats: dict[str, Any], cells: list[str]) -> None:
    stats["runs"] += 1
    for name, column in SUMMED.items():
        index = COLUMNS.index(column)
        value = _number(cells[index]) if index < len(cells) else None
        if value is None:
            stats["missing"][name] += 1
        else:
            stats[name] += value


def _finish(stats: dict[str, Any]) -> dict[str, Any]:
    done: dict[str, Any] = {"runs": stats["runs"]}
    done.update({name: _plain(stats[name]) for name in SUMMED})
    done["missing"] = dict(stats["missing"])
    return done


def _data_rows(text: str) -> list[list[str]]:
    """The cells of each data row under the exact header row."""
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == HEADER]
    if not starts:
        raise ValueError("the cost log table header row was not found")
    start = starts[0]
    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.strip().startswith("|"):
            break
        rows.append(_cells(line))
    return rows


def summarize(text: str) -> dict[str, Any]:
    """Group the cost log rows by "What ran" and sum them; ValueError if there is no table."""
    groups: dict[str, dict[str, Any]] = {}
    total = _empty_stats()
    for cells in _data_rows(text):
        name = cells[WHAT_RAN] if WHAT_RAN < len(cells) else ""
        _add_row(groups.setdefault(name, _empty_stats()), cells)
        _add_row(total, cells)
    return {
        "groups": {name: _finish(stats) for name, stats in groups.items()},
        "total": _finish(total),
    }


def _table_row(name: str, stats: dict[str, Any]) -> str:
    cells = [name, stats["runs"]]
    cells += [stats[key] for key in SUMMED if key != "credits"]
    cells += [stats["credits"], sum(stats["missing"].values())]
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def render(summary: dict[str, Any]) -> str:
    """The summary as a markdown table with a last row named Total."""
    lines = ["| " + " | ".join(TABLE_COLUMNS) + " |", "|" + "---|" * len(TABLE_COLUMNS)]
    lines += [_table_row(name, stats) for name, stats in summary["groups"].items()]
    lines.append(_table_row("Total", summary["total"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Print the summary of the cost log at PATH; exit 2 when it cannot be read or parsed."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", help="the cost log markdown file")
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = parser.parse_args(argv)
    try:
        summary = summarize(Path(args.path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        sys.stderr.write(f"cost_summary: {args.path}: {error}\n")
        return 2
    sys.stdout.write((json.dumps(summary, indent=2) if args.json else render(summary)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
