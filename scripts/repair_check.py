#!/usr/bin/env python3
"""Check that a repair merge request fixes the jobs the autoheal issue listed.

``request_fix`` opens an issue with a "Failed jobs:" list, the Duo flow opens a merge request, and
this script compares the two with no model involved: every job named in the issue must have the
status ``success`` in the latest pipeline of the merge request. A job that did not run in that
pipeline is ``missing``, which is not a pass. Only the public GitLab REST API v4 is read.

Usage: python -m scripts.repair_check --project ID --issue IID --mr IID
Exit codes: 0 every listed job is fixed, 1 not (the JSON says which), 2 the API or the issue
could not be read (fails closed; nothing is printed on stdout).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from scripts.afaw_state.facts import MAX_PAGES, PAGE_SIZE, FactsError, http_get_json

DEFAULT_API_URL = "https://gitlab.com/api/v4"
_HEADER = "Failed jobs:"
_BULLET = re.compile(r"^- `([^`]+)` \(stage [^)]*\)\s*$")


def failed_jobs(issue_description: str) -> list[str]:
    """The job names listed under "Failed jobs:" in an autoheal issue, in order, without repeats.

    The list is the run of lines like ``- `lint` (stage verify)`` right after the header; it
    ends at the first line of another shape.
    """
    _, found, rest = issue_description.partition(_HEADER)
    if not found:
        return []
    names: list[str] = []
    for line in rest.splitlines()[1:]:
        match = _BULLET.match(line.strip())
        if not match:
            break
        if match.group(1) not in names:
            names.append(match.group(1))
    return names


def check(failed: Sequence[str], jobs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare the listed job names with the jobs of the repair pipeline.

    ``fixed``: the last attempt (highest job id) of that name has the status success.
    ``still_failing``: a job with that name ran and its last attempt is not a success.
    ``missing``: no job with that name ran. ``ok`` needs at least one listed job and nothing else.
    """
    last: dict[str, Mapping[str, Any]] = {}
    for job in jobs:
        name = job["name"]
        if name not in last or job["id"] > last[name]["id"]:
            last[name] = job
    fixed = [n for n in failed if n in last and last[n]["status"] == "success"]
    still_failing = [n for n in failed if n in last and last[n]["status"] != "success"]
    missing = [n for n in failed if n not in last]
    return {
        "ok": bool(failed) and not still_failing and not missing,
        "fixed": fixed,
        "still_failing": still_failing,
        "missing": missing,
    }


def _pages(get_json: Callable[[str], Any], url: str) -> list[Any]:
    sep = "&" if "?" in url else "?"
    items: list[Any] = []
    for page in range(1, MAX_PAGES + 1):
        batch = get_json(f"{url}{sep}per_page={PAGE_SIZE}&page={page}")
        if not isinstance(batch, list):
            raise FactsError(f"{url.split('?')[0]}: expected a list")
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            return items
    raise FactsError(f"{url.split('?')[0]}: more than {MAX_PAGES} pages; refusing a partial list")


def _issue_failed_jobs(get_json: Callable[[str], Any], base: str, issue: int) -> list[str]:
    body = get_json(f"{base}/issues/{issue}")
    description = body.get("description") if isinstance(body, dict) else None
    if not isinstance(description, str):
        raise FactsError(f"issue #{issue}: no description to read")
    names = failed_jobs(description)
    if not names:
        raise FactsError(f"issue #{issue}: no '{_HEADER}' list found")
    return names


def _latest_pipeline_jobs(
    get_json: Callable[[str], Any], base: str, mr: int
) -> list[Mapping[str, Any]]:
    pipelines = _pages(get_json, f"{base}/merge_requests/{mr}/pipelines")
    if not pipelines:
        return []
    latest = max(pipelines, key=lambda p: p["id"])
    return _pages(get_json, f"{base}/pipelines/{latest['id']}/jobs?include_retried=true")


def run(get_json: Callable[[str], Any], api_url: str, project: str, issue: int, mr: int) -> int:
    """Print the result as JSON and return the exit code."""
    base = f"{api_url.rstrip('/')}/projects/{urllib.parse.quote(project, safe='')}"
    try:
        names = _issue_failed_jobs(get_json, base, issue)
        result = check(names, _latest_pipeline_jobs(get_json, base, mr))
    except (FactsError, urllib.error.URLError, KeyError, TypeError, ValueError) as error:
        print(f"repair_check: could not decide: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def main(argv: Sequence[str] | None = None, get_json: Callable[[str], Any] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--project", default=os.environ.get("CI_PROJECT_ID"), help="project id")
    parser.add_argument("--issue", type=int, required=True, help="autoheal issue iid")
    parser.add_argument("--mr", type=int, required=True, help="repair merge request iid")
    parser.add_argument("--api-url", default=os.environ.get("CI_API_V4_URL", DEFAULT_API_URL))
    args = parser.parse_args(argv)
    if not args.project:
        print("repair_check: --project is required (or CI_PROJECT_ID)", file=sys.stderr)
        return 2
    fetch = get_json or (lambda url: http_get_json(url, {}))
    return run(fetch, args.api_url, str(args.project), args.issue, args.mr)


if __name__ == "__main__":
    raise SystemExit(main())
