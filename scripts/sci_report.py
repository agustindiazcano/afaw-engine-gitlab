"""SCI of the development flows, from the job seconds the GitLab API reports (ADR 0009).

A flow is one merged merge request: its own pipelines plus the pipeline of ``main`` that ran on
its merge commit. Energy uses the Cloud Carbon Footprint figures for a 2 vCPU GCP runner and the
Google Cloud grid intensity of the two hosted-runner regions, so every result is a range, never a
point. M (embodied) is not estimated, so the score is labelled "SCI without M". The energy of the
model behind GitLab Duo is not measured and is not in any figure.

Usage:
    python -m scripts.sci_report --project 88052530 [--recent 30] [--json OUT] [--markdown OUT]
The project is public, so no token is needed to read jobs.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.afaw_state.facts import FactsError, http_get_json
from scripts.sci_estimate import estimate

API = "https://gitlab.com/api/v4"
VCPUS = 2
PUE = 1.1
MIN_WATTS = 0.71
MAX_WATTS = 4.26
GRID_LOW = 343  # us-east5, g CO2eq per kWh, Google Cloud region data 2025
GRID_HIGH = 579  # us-east1


def flow_seconds(jobs: Sequence[Mapping[str, Any]]) -> float:
    """Sum of the durations the API reports; a job with no duration adds nothing."""
    return float(sum(j["duration"] for j in jobs if j.get("duration") is not None))


def sci_range(seconds: float) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Low (0.71 W, 343 g/kWh), middle (50 % utilization, 461) and high (4.26 W, 579)."""

    def run(utilization: float, grid: float) -> dict[str, Any]:
        return estimate(seconds, VCPUS, utilization, MIN_WATTS, MAX_WATTS, PUE, grid, 0, 1)

    return run(0, GRID_LOW), run(0.5, (GRID_LOW + GRID_HIGH) / 2), run(1, GRID_HIGH)


class Api:
    """Reads the public GitLab API."""

    def __init__(self, project: str, base: str = API) -> None:
        self.root = f"{base}/projects/{project}"

    def get(self, path: str) -> Any:
        return http_get_json(self.root + path, {})


def flow_pipelines(api: Any, iid: int) -> list[int]:
    """Pipelines of the merge request, then the main pipeline of its merge commit if merged."""
    ids = [int(p["id"]) for p in api.get(f"/merge_requests/{iid}/pipelines?per_page=100")]
    mr = api.get(f"/merge_requests/{iid}")
    sha = mr.get("merge_commit_sha")
    if mr.get("state") == "merged" and sha:
        ids += [int(p["id"]) for p in api.get(f"/pipelines?sha={sha}&ref=main") or []]
    return ids


def measure(api: Any, iid: int) -> tuple[int, float]:
    """Number of pipelines and job seconds of one flow."""
    ids = flow_pipelines(api, iid)
    jobs: list[Mapping[str, Any]] = []
    for pid in ids:
        jobs += api.get(f"/pipelines/{pid}/jobs?per_page=100")
    return len(ids), flow_seconds(jobs)


def render(rows: Sequence[tuple[str, int, float]]) -> str:
    """Markdown table: one row per flow with the SCI range, then the assumptions."""
    lines = [
        "| Flow | Pipelines | Job seconds | Energy (Wh, low to high) | gCO2eq (low to high) |",
        "|---|---|---|---|---|",
    ]
    total = 0.0
    for name, pipelines, seconds in rows:
        total += seconds
        low, _, high = sci_range(seconds)
        lines.append(
            f"| {name} | {pipelines} | {seconds:.0f} | {low['energy_kwh'] * 1000:.2f} to "
            f"{high['energy_kwh'] * 1000:.2f} | {low['sci_g_per_unit']:.3f} to "
            f"{high['sci_g_per_unit']:.3f} |"
        )
    low, _, high = sci_range(total)
    lines.append(
        f"| **All {len(rows)} flows** | | {total:.0f} | {low['energy_kwh'] * 1000:.2f} to "
        f"{high['energy_kwh'] * 1000:.2f} | {low['sci_g_per_unit']:.3f} to "
        f"{high['sci_g_per_unit']:.3f} |"
    )
    lines += [
        "",
        f"Assumptions: {VCPUS} vCPU runner, {MIN_WATTS} to {MAX_WATTS} W per vCPU and PUE {PUE} "
        f"(Cloud Carbon Footprint), grid {GRID_LOW} to {GRID_HIGH} gCO2eq/kWh (Google Cloud "
        "region data 2025, the two hosted-runner regions). R is one merged merge request. "
        "SCI without M: embodied emissions are not estimated. The energy of GitLab Duo's model "
        "is not measured and is not included; GitLab Credits are an accounting unit, not energy.",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Measure the most recent merged merge requests and write the table and the JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--recent", type=int, default=30)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)
    api = Api(args.project)
    try:
        merged = api.get(f"/merge_requests?state=merged&per_page={args.recent}&order_by=updated_at")
        rows = []
        for mr in merged:
            pipelines, seconds = measure(api, int(mr["iid"]))
            rows.append((f"!{mr['iid']}", pipelines, seconds))
    except FactsError as exc:
        print(f"sci_report: {exc}", file=sys.stderr)
        return 2
    table = render(rows)
    if args.markdown:
        args.markdown.write_text(table + "\n", encoding="utf-8")
    if args.json:
        total = sum(r[2] for r in rows)
        low, mid, high = sci_range(total)
        args.json.write_text(
            json.dumps(
                {
                    "flows": len(rows),
                    "job_seconds": total,
                    "gco2eq_low": low["sci_g_per_unit"],
                    "gco2eq_mid": mid["sci_g_per_unit"],
                    "gco2eq_high": high["sci_g_per_unit"],
                    "per_flow": [{"flow": n, "pipelines": p, "job_seconds": s} for n, p, s in rows],
                    "assumptions": "SCI without M; Duo model energy not measured",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
