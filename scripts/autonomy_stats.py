"""Count the merge requests made and merged by agents, from the GitLab REST API.

A merge request is *agent only* when every commit is authored by a service account address. It is
*guard merged* when it is agent only, merged, and GitLab recorded the system note "enabled an
automatic merge". A person can also enable that on their own merge request in the UI, so the note
counts only together with agent-only authorship. The guard uses a person's token, so the note
carries that person's name: it proves no one clicked, not that no person's token was involved.
Nothing here is declared by an agent.

Usage:
    GITLAB_TOKEN=... python -m scripts.autonomy_stats --project 88052530 \
        [--json OUT] [--markdown OUT]
The token is needed to read system notes; it is read from the environment and never written.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.afaw_state.facts import MAX_PAGES, PAGE_SIZE, FactsError, http_get_json
from scripts.service_accounts import is_service_account_email

AUTO_MERGE_NOTE = "enabled an automatic merge"
API = "https://gitlab.com/api/v4"


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def classify(
    mr: Mapping[str, Any],
    commits: Sequence[Mapping[str, Any]],
    notes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """One row for a merge request: who wrote it, how it was merged, how long it took."""
    agent_only = bool(commits) and all(
        is_service_account_email(str(c.get("author_email", ""))) for c in commits
    )
    auto_merged = any(n.get("system") and AUTO_MERGE_NOTE in str(n.get("body", "")) for n in notes)
    minutes: float | None = None
    if mr.get("merged_at"):
        minutes = (_parse(mr["merged_at"]) - _parse(mr["created_at"])).total_seconds() / 60
    return {
        "iid": mr["iid"],
        "state": mr["state"],
        "agent_only": agent_only,
        "auto_merged": auto_merged,
        "minutes_to_merge": minutes,
    }


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Totals over the rows; the median is None when no agent-only merge request was merged."""
    merged = [r for r in rows if r["state"] == "merged"]
    agent_merged = [r for r in merged if r["agent_only"]]
    times = [r["minutes_to_merge"] for r in agent_merged if r["minutes_to_merge"] is not None]
    return {
        "total": len(rows),
        "merged": len(merged),
        "closed": sum(1 for r in rows if r["state"] == "closed"),
        "opened": sum(1 for r in rows if r["state"] == "opened"),
        "agent_only": sum(1 for r in rows if r["agent_only"]),
        "agent_only_merged": len(agent_merged),
        "guard_merged": sum(1 for r in agent_merged if r["auto_merged"]),
        "median_minutes_agent_only_merged": statistics.median(times) if times else None,
    }


def render(summary: Mapping[str, Any]) -> str:
    """The summary as a Markdown table."""
    median = summary["median_minutes_agent_only_merged"]
    shown = "not available" if median is None else f"{median:.1f}"
    lines = [
        "| Measure | Value |",
        "|---|---|",
        f"| Merge requests | {summary['total']} |",
        "| Merged / closed / open | "
        f"{summary['merged']} / {summary['closed']} / {summary['opened']} |",
        f"| Made only by agents (all commits by a service account) | {summary['agent_only']} |",
        f"| Of those, merged | {summary['agent_only_merged']} |",
        f"| Of those, merged with a recorded automatic merge | {summary['guard_merged']} |",
        f"| Median minutes from open to merge, agent-only merged | {shown} |",
    ]
    return "\n".join(lines) + "\n"


def _pages(get: Callable[[str], Any], base: str, path: str, extra: str = "") -> list[Any]:
    items: list[Any] = []
    for page in range(1, MAX_PAGES + 1):
        query = urllib.parse.urlencode({"per_page": PAGE_SIZE, "page": page})
        batch = get(f"{base}/{path}?{query}{extra}")
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            return items
    raise FactsError(f"{path}: more than {MAX_PAGES} pages; refusing to use a partial list")


def collect(get: Callable[[str], Any], project: str) -> list[dict[str, Any]]:
    """Read every merge request, its commits and its notes, and classify each."""
    base = f"{API}/projects/{project}"
    rows = []
    for mr in _pages(get, base, "merge_requests", "&state=all"):
        iid = mr["iid"]
        commits = _pages(get, base, f"merge_requests/{iid}/commits")
        notes = _pages(get, base, f"merge_requests/{iid}/notes")
        rows.append(classify(mr, commits, notes))
    return rows


def main(argv: list[str] | None = None) -> int:
    """Print the stats; optionally write them as JSON and Markdown."""
    parser = argparse.ArgumentParser(description="Stats of merge requests made by agents.")
    parser.add_argument("--project", required=True, help="numeric project id")
    parser.add_argument("--json", type=Path, help="write the summary and rows as JSON")
    parser.add_argument("--markdown", type=Path, help="write the summary table")
    args = parser.parse_args(argv)
    token = os.environ.get("GITLAB_TOKEN", "")
    if not token:
        sys.stderr.write("ERROR: GITLAB_TOKEN is not set; system notes need it\n")
        return 2
    headers = {"PRIVATE-TOKEN": token}
    rows = collect(lambda url: http_get_json(url, headers), args.project)
    summary = summarize(rows)
    text = render(summary)
    sys.stdout.write(text)
    if args.json:
        args.json.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")
    if args.markdown:
        args.markdown.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
