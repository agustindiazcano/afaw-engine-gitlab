#!/usr/bin/env python3
"""Print one markdown row for docs/submission/cost-log.md from the public GitLab API.

Given a merge request (``--mr``) or pipelines by id (``--pipeline``, repeatable, for a Duo
session), it lists the pipelines, the job minutes and seconds and the retries, reusing the
parsers of collect_facts. The credit columns are left as ``human``: GitLab Credits are read by
hand from the credits dashboard. A value that cannot be measured is ``null``, never zero.

Usage:
    python -m scripts.cost_log --mr 9 --what "Developer Flow" --session <url>
    python -m scripts.cost_log --pipeline 2985662569 --what "Fix CI/CD Pipeline"
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import timedelta, timezone
from typing import Any

from scripts.afaw_state.derive import require_ts
from scripts.afaw_state.facts import FactsError, GitLab, gitlab_ci_facts

GMT_MINUS_3 = timezone(timedelta(hours=-3))
COLUMNS = (
    "Date and time (GMT-3)",
    "What ran",
    "Session URL",
    "Merge request",
    "Credits before",
    "Credits after",
    "Delta",
    "Pipelines",
    "Job minutes",
    "Job seconds",
    "Retries",
    "Notes",
)
HUMAN = "human"


class CostLogError(RuntimeError):
    """The row cannot be built from measured data."""


def _cell(value: Any) -> str:
    return "null" if value is None else str(value)


def row_for(
    gitlab: GitLab,
    mr_iid: int | None = None,
    pipeline_ids: Sequence[int] = (),
    what: str = "",
    session: str = "",
) -> str:
    """One markdown table row for a merge request or for the given pipelines."""
    pipelines: list[Mapping[str, Any]] = []
    if mr_iid is not None:
        pipelines += gitlab.mr_pipelines(mr_iid)
    for pipeline_id in pipeline_ids:
        pipelines.append(gitlab.pipeline(pipeline_id))
    if not pipelines:
        raise CostLogError("no pipeline found for the given merge request or ids")
    jobs = {p["id"]: gitlab.jobs(p["id"]) for p in pipelines}
    ci = gitlab_ci_facts(pipelines, jobs)["ci"]
    first = min(require_ts(p["created_at"]) for p in pipelines).astimezone(GMT_MINUS_3)
    links = ", ".join(f"[{p['id']}]({p['web_url']})" for p in pipelines)
    cells = [
        first.strftime("%Y-%m-%d %H:%M"),
        what,
        session,
        f"!{mr_iid}" if mr_iid is not None else "",
        HUMAN,
        HUMAN,
        HUMAN,
        links,
        _cell(ci["job_minutes"]),
        _cell(ci["job_seconds"]),
        _cell(ci["retries"]),
        "",
    ]
    return "| " + " | ".join(cells) + " |"


def main(argv: list[str] | None = None) -> int:
    """Print the row; exit 2 when it cannot be built from the API."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mr", type=int, help="merge request iid")
    parser.add_argument("--pipeline", type=int, action="append", default=[], help="pipeline id")
    parser.add_argument("--what", default="", help="what ran, e.g. the flow name")
    parser.add_argument("--session", default="", help="session URL")
    parser.add_argument("--api-url", default="https://gitlab.com/api/v4")
    parser.add_argument("--project", default=os.environ.get("CI_PROJECT_ID", "88052530"))
    args = parser.parse_args(argv)
    if args.mr is None and not args.pipeline:
        sys.stderr.write("cost_log: give --mr or --pipeline\n")
        return 2
    try:
        gitlab = GitLab(args.api_url, args.project, None)
        sys.stdout.write(row_for(gitlab, args.mr, args.pipeline, args.what, args.session) + "\n")
    except (CostLogError, FactsError) as error:
        sys.stderr.write(f"cost_log: {error}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
