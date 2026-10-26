"""The experiments and environment pages of the dashboard: measured data, charts and tables.

The data is ``docs/data/experiments.json``: every figure in it was read from the GitLab API, a CI
job or a command, and every section names its source. The pages are static HTML with inline SVG
charts, a table view behind every chart and no script. The environment page computes the Software
Carbon Intensity with ``scripts.sci_estimate``, the tool the Duo Developer Flow wrote, and prints
the assumptions next to the result.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from typing import Any

from scripts.sci_estimate import estimate

from . import brand
from .render import CSS, SERIES_CSS

CSS_EXTRA = """
figure.chart{background:var(--card);border:1px solid var(--line);border-radius:8px;
  padding:12px 16px;margin:0 0 20px}
figure.chart h3{margin:0 0 8px;font-size:15px}
figure.chart figcaption{color:var(--muted);font-size:12px;margin-top:8px}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;margin:0 0 8px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{width:12px;height:12px;border-radius:3px;display:inline-block}
.legend .s1{background:var(--series-1)}
.legend .s2{background:var(--series-2)}
svg.bars{width:100%;height:auto;max-width:760px}
svg.bars text{fill:var(--ink);font:12px system-ui,-apple-system,"Segoe UI",sans-serif}
svg.bars .lab{fill:var(--muted)}
svg.bars .bar.s1{fill:var(--series-1)}
svg.bars .bar.s2{fill:var(--series-2)}
table.chaos td{white-space:normal;vertical-align:top;min-width:140px}
details.table{margin-top:8px}
details.table summary{cursor:pointer;color:var(--muted)}
.note{color:var(--muted)}
ul.limits{margin:8px 0 0;padding-left:20px}
"""

WIDTH = 760
LABEL_W = 270
VALUE_W = 56
BAR_H = 14
SERIES_GAP = 2
ROW_GAP = 14


def _fmt(value: float) -> str:
    return f"{value:g}"


def bars(
    rows: Sequence[tuple[str, Sequence[float]]],
    series: Sequence[str],
    unit: str,
    max_value: float | None,
    label: str = "",
) -> str:
    """Horizontal bars, one group per row and one bar per series, with the value at the end."""
    area = WIDTH - LABEL_W - VALUE_W
    top = max_value or max((v for _, values in rows for v in values), default=1.0) or 1.0
    group_h = len(series) * BAR_H + (len(series) - 1) * SERIES_GAP
    height = max(len(rows) * (group_h + ROW_GAP) + 4, 24)
    parts = [
        f'<svg class="bars" viewBox="0 0 {WIDTH} {height}" role="img" '
        f'aria-label="{escape(label)}" preserveAspectRatio="xMinYMin meet">'
    ]
    for i, (name, values) in enumerate(rows):
        y0 = 4 + i * (group_h + ROW_GAP)
        parts.append(
            f'<text class="lab" x="{LABEL_W - 8}" y="{y0 + group_h / 2 + 4:.1f}" '
            f'text-anchor="end">{escape(name)}</text>'
        )
        for j, value in enumerate(values):
            y = y0 + j * (BAR_H + SERIES_GAP)
            width = max(0.0, value / top * area)
            if width > 0:
                tip = f"{escape(name)}, {escape(series[j])}: {_fmt(value)} {escape(unit)}"
                parts.append(
                    f'<rect class="bar s{j + 1}" x="{LABEL_W}" y="{y}" width="{width:.1f}" '
                    f'height="{BAR_H}" rx="4"><title>{tip}</title></rect>'
                )
            parts.append(
                f'<text x="{LABEL_W + width + 6:.1f}" y="{y + BAR_H - 3}">{_fmt(value)}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _table(head: Sequence[str], body: Sequence[Sequence[str]], caption: str = "Table view") -> str:
    th = "".join(f"<th>{escape(h)}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row) + "</tr>" for row in body)
    return (
        f'<details class="table"><summary>{escape(caption)}</summary>'
        f'<div class="scroll"><table><tr>{th}</tr>{tr}</table></div></details>'
    )


def chart(
    title: str,
    rows: Sequence[tuple[str, Sequence[float]]],
    series: Sequence[str],
    unit: str,
    max_value: float | None,
    source: str = "",
) -> str:
    """A titled chart: legend (two series or more), the bars, a table view and the source."""
    legend = (
        '<div class="legend">'
        + "".join(f'<span><i class="s{j + 1}"></i>{escape(s)}</span>' for j, s in enumerate(series))
        + "</div>"
        if len(series) > 1
        else ""
    )
    label = f"{title}, in {unit}: " + "; ".join(
        f"{n}: " + ", ".join(f"{s} {_fmt(v)}" for s, v in zip(series, values, strict=True))
        for n, values in rows
    )
    table = _table(
        ["Item", *[f"{s} ({unit})" for s in series]],
        [[n, *[_fmt(v) for v in values]] for n, values in rows],
    )
    caption = f"<figcaption>Source: {escape(source)}</figcaption>" if source else ""
    return (
        f'<figure class="chart"><h3>{escape(title)}</h3>{legend}'
        f"{bars(rows, series, unit, max_value, label)}{table}{caption}</figure>"
    )


def chaos_table(rows: Sequence[Mapping[str, Any]]) -> str:
    """Faults injected on purpose: what was expected, what was seen, and whether it held."""
    head = "".join(f"<th>{h}</th>" for h in ("Id", "Fault", "Expected", "Observed", "Result"))
    body = "".join(
        "<tr>"
        + "".join(f"<td>{escape(str(r[k]))}</td>" for k in ("id", "fault", "expected", "observed"))
        + f"<td>{'Held' if r['held'] else 'Did not hold'}</td></tr>"
        for r in rows
    )
    return f'<div class="scroll"><table class="chaos"><tr>{head}</tr>{body}</table></div>'


def _tile(value: str, label: str) -> str:
    return f'<div class="tile"><b>{escape(value)}</b><span>{escape(label)}</span></div>'


def _page(title: str, intro: str, body: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{brand.NAME} · {escape(title)}</title>"
        f"<style>{SERIES_CSS}{CSS}{brand.CSS}{CSS_EXTRA}</style></head><body>{brand.nav()}<main>"
        f'<h1>{escape(title)}</h1><p class="meta">{escape(intro)}</p>{body}'
        f"</main>{brand.footer()}</body></html>\n"
    )


def _handoff(h: Mapping[str, Any]) -> str:
    """The hands-off loop: autonomy counts, the nine stages, the repair chain and the limits."""
    a = h["autonomy"]
    tiles = (
        _tile(f"{a['agent_only']} of {a['merge_requests']}", "Merge requests made only by agents")
        + _tile(str(a["guard_merged"]), "Agent-only, merged with a recorded automatic merge")
        + _tile(str(a["median_minutes"]), "Median minutes, open to merge (agent-only, merged)")
    )
    stages = _table(
        ["Stage", "Issue", "Merge request", "What Duo changed"],
        [[s["stage"], f"#{s['issue']}", f"!{s['mr']}", s["what"]] for s in h["stages"]],
        "The nine stages, each with a merge request written by Duo",
    )
    chain = _table(
        ["Link", "Time (UTC)", "Since the previous link"],
        [[c["link"], c["utc"], c["since"]] for c in h["chain"]],
        "Repair chain: a failing live check to a repaired, redeployed app",
    )
    limits = "".join(f"<li>{escape(text)}</li>" for text in h["limits"])
    return (
        f"<h2>Hands-off loop</h2>"
        f'<p class="meta">Counts read from the GitLab API on {escape(a["read_on"])}.</p>'
        f'<div class="tiles">{tiles}</div>{stages}{chain}'
        f"<h3>What this does not prove</h3><ul>{limits}</ul>"
    )


def experiments_page(data: Mapping[str, Any]) -> str:
    """Coverage, mutation score and timings of the experiments, with the merges by the guard."""
    builds = data["hard_builds"]
    passed = sum(b["hidden_passed"] for b in builds)
    total = sum(b["hidden_total"] for b in builds)
    repairs = data["repairs"]
    credits = data["credits"]
    tiles = (
        _tile(f"{passed} of {total}", "Hidden acceptance tests passed")
        + _tile(f"{repairs['repaired']} of {repairs['planted']}", "Planted defects repaired")
        + _tile(
            str(data["handoff"]["autonomy"]["guard_merged"]),
            "Merges by merge_guard (agent-only, automatic merge recorded)",
        )
        + _tile(
            f"{credits['used']:.2f} of {credits['budget']}", "GitLab Credits used, read by hand"
        )
    )
    cov, mut, mins = data["coverage"], data["mutation"], data["minutes"]
    charts = (
        chart(
            "Coverage by file, before and after the tests Duo wrote",
            [(r["label"], [r["before"], r["after"]]) for r in cov["rows"]],
            ["Before", "After"],
            cov["unit"],
            100.0,
            cov["source"],
        )
        + chart(
            "Mutation score, before and after",
            [(r["label"], [r["before"], r["after"]]) for r in mut["rows"]],
            ["Before", "After"],
            mut["unit"],
            100.0,
            mut["source"],
        )
        + chart(
            "Minutes from the request to the result",
            [(r["label"], [r["value"]]) for r in mins["rows"]],
            ["Minutes"],
            mins["unit"],
            None,
            mins["source"],
        )
    )
    merges = _table(
        ["Merge request", "Merged (UTC)"],
        [[f"!{m['mr']}", m["merged_utc"]] for m in data["guard_merges"]],
        "The first nine merges by merge_guard, with their times",
    )
    hard = _table(
        ["Tool", "Merge request", "Hidden tests", "Tests Duo wrote", "Coverage by them (%)"],
        [
            [
                b["tool"],
                f"!{b['mr']}",
                f"{b['hidden_passed']} of {b['hidden_total']}",
                str(b["own_tests"]),
                str(b["coverage"]),
            ]
            for b in builds
        ],
        "Tools built from a specification and judged by tests Duo never saw",
    )
    body = (
        f'<div class="tiles">{tiles}</div><h2>Charts</h2>{charts}'
        f"<h2>Merges and builds</h2>{merges}{hard}"
        f"{_handoff(data['handoff'])}"
        f"<h2>Chaos and security</h2>{chaos_table(data['chaos'])}"
        f'<p class="note">{escape(data["note"])}</p>'
    )
    return _page("Experiments and benchmarks", f"Measured on {data['as_of']}.", body)


def _run(run: Mapping[str, Any], assumptions: Mapping[str, Any], grid: float) -> Mapping[str, Any]:
    return estimate(
        job_seconds=run["job_seconds"],
        vcpus=assumptions["vcpus"],
        utilization=assumptions["utilization"],
        min_watts=assumptions["min_watts"],
        max_watts=assumptions["max_watts"],
        pue=assumptions["pue"],
        grid_g_per_kwh=grid,
        embodied_g=assumptions["embodied_g"],
        functional_units=assumptions["functional_units"],
    )


def environment_page(data: Mapping[str, Any]) -> str:
    """The SCI of one mutation run with each tool, from CI seconds and declared assumptions."""
    env = data["environment"]
    runs, grids, a = env["runs"], env["grids"], env["assumptions"]
    series = [f"{g['region']} ({g['g_per_kwh']} g/kWh)" for g in grids]
    estimates = {r["tool"]: [_run(r, a, g["g_per_kwh"]) for g in grids] for r in runs}
    carbon = chart(
        "Estimated gCO2eq of one mutation run, by grid intensity",
        [(t, [round(e["sci_g_per_unit"], 3) for e in es]) for t, es in estimates.items()],
        series,
        "gCO2eq per run",
        None,
        env["source"],
    )
    seconds = chart(
        "Runner time of one mutation run",
        [(r["tool"], [r["job_seconds"]]) for r in runs],
        ["Job seconds"],
        "seconds",
        None,
        "CI job seconds measured on the runner, docs/submission/mutation-tools-measurement.md",
    )
    slow = max(runs, key=lambda r: r["job_seconds"])
    fast = min(runs, key=lambda r: r["job_seconds"])
    ratio = slow["job_seconds"] / fast["job_seconds"]
    statement = (
        f"{fast['tool']} used {ratio:.1f} times less runner time than {slow['tool']} "
        f"({fast['job_seconds']} s against {slow['job_seconds']} s) and killed "
        f"{fast['score']} % of the mutants against {slow['score']} %."
    )
    energy = _table(
        ["Tool", "Job seconds", "Energy (Wh)", "Mutants killed (%)"],
        [
            [
                r["tool"],
                str(r["job_seconds"]),
                f"{estimates[r['tool']][0]['energy_kwh'] * 1000:.3f}",
                str(r["score"]),
            ]
            for r in runs
        ],
        "Energy per run",
    )
    assumptions = _table(
        ["Assumption", "Value"],
        [
            ["vCPUs of the runner", str(a["vcpus"])],
            ["CPU utilization", str(a["utilization"])],
            ["Watts per vCPU, minimum and maximum", f"{a['min_watts']} and {a['max_watts']}"],
            ["PUE", str(a["pue"])],
            [
                "Grid intensity, gCO2eq per kWh",
                ", ".join(f"{g['region']} {g['g_per_kwh']}" for g in grids),
            ],
            ["Embodied emissions (M)", f"{a['embodied_g']} g, not estimated"],
            ["Functional unit (R)", f"{a['functional_units']} mutation run"],
        ],
        "Assumptions behind every number",
    )
    limits = "".join(f"<li>{escape(x)}</li>" for x in env["limits"])
    body = (
        f"<p>{escape(statement)}</p>{carbon}{seconds}<h2>Method and limits</h2>"
        "<p>SCI = (O + M) per R, with O = E x I, as the Green Software Foundation specification "
        "defines it. The numbers come from <code>scripts/sci_estimate.py</code>, written by the "
        f"Duo Developer Flow, and the inputs are printed here.</p>{energy}{assumptions}"
        f'<ul class="limits">{limits}</ul>'
    )
    return _page("Environmental impact (SCI)", f"Estimated on {data['as_of']}.", body)


def extra_outputs(data: Mapping[str, Any] | None) -> dict[str, str]:
    """The two pages, or nothing when the data file is not in the repository."""
    if not data:
        return {}
    return {
        "experiments.html": experiments_page(data),
        "environment.html": environment_page(data),
    }
