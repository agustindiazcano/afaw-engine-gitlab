#!/usr/bin/env python3
"""Write ``build/AFAW_TELEMETRY.md``: one block per self-healing event, read from the GitLab API.

An event starts with an issue labelled ``afaw-autoheal`` (opened by ``request_fix``) and ends with
the merge of the merge request that closes it. Each block lists the same fields:

* timestamp and branch: creation time of the issue and the branch it names;
* trigger: the failed jobs the issue lists under "Failed jobs:";
* root cause: the description of the repair merge request, quoted verbatim, never summarised;
* remediation: the files that merge request changed;
* validation: merge time, minutes from issue to merge, status of the pipeline of the merge commit.

A field with no source says ``not available``; nothing is estimated. ``build_block`` and ``render``
are pure functions; the API is read only at the edge (``collect_blocks``, ``main``). The file is
generated and never committed.

Usage: python -m scripts.telemetry_report --project ID --out build/AFAW_TELEMETRY.md
Exit codes: 0 written, 2 the API could not be read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.afaw_state.facts import MAX_PAGES, PAGE_SIZE, FactsError

LABEL = "afaw-autoheal"
NOT_AVAILABLE = "not available"
DEFAULT_API_URL = "https://gitlab.com/api/v4"
TIMEOUT = 30
TITLE = "# AFAW telemetry"
_BRANCH = re.compile(r"A pipeline failed on branch `([^`]+)`")
_JOB = re.compile(r"^- `([^`]+)`", re.MULTILINE)
_BACKTICKS = re.compile(r"`+")

GetJson = Callable[[str], Any]


def _longest_run(text: str) -> int:
    return max((len(run) for run in _BACKTICKS.findall(text)), default=0)


def inline_code(text: str) -> str:
    """``text`` as a Markdown code span that a backtick inside it cannot end."""
    fence = "`" * (_longest_run(text) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def fenced_block(text: str) -> str:
    """``text`` verbatim in a code fence longer than any run of backticks inside it."""
    fence = "`" * max(3, _longest_run(text) + 1)
    return f"{fence}text\n{text}\n{fence}"


def _branch(issue: Mapping[str, Any]) -> str:
    match = _BRANCH.search(issue.get("description") or "")
    return inline_code(match.group(1)) if match else NOT_AVAILABLE


def _trigger(issue: Mapping[str, Any]) -> str:
    text = issue.get("description") or ""
    _, found, after = text.partition("Failed jobs:")
    names = _JOB.findall(after.split("\n\n", 1)[0] if found else "")
    return ", ".join(inline_code(n) for n in names) if names else NOT_AVAILABLE


def _remediation(changes: Sequence[Mapping[str, Any]] | None) -> str:
    if changes is None:
        return NOT_AVAILABLE
    paths = [c.get("new_path") or c["old_path"] for c in changes]
    noun = "file" if len(paths) == 1 else "files"
    listing = ", ".join(inline_code(p) for p in paths)
    return f"{len(paths)} {noun}: {listing}" if paths else f"0 {noun}"


def _minutes(created_at: str | None, merged_at: str | None) -> str:
    if not created_at or not merged_at:
        return NOT_AVAILABLE
    seconds = (
        datetime.fromisoformat(merged_at) - datetime.fromisoformat(created_at)
    ).total_seconds()
    return f"{seconds / 60:.1f}"


def build_block(
    issue: Mapping[str, Any],
    mr: Mapping[str, Any] | None,
    changes: Sequence[Mapping[str, Any]] | None,
    pipeline: Mapping[str, Any] | None,
) -> str:
    """One Markdown block for an issue and its repair merge request (``None`` if there is none)."""
    merged_at = mr.get("merged_at") if mr else None
    description = (mr.get("description") or "") if mr else ""
    status = pipeline.get("status") if pipeline and merged_at else None
    lines = [
        f"## [#{issue['iid']}]({issue.get('web_url', '')}) {issue.get('title', '')}",
        "",
        f"**Timestamp:** {issue.get('created_at') or NOT_AVAILABLE}",
        f"**Branch:** {_branch(issue)}",
        f"**Trigger:** {_trigger(issue)}",
    ]
    if description.strip():
        lines += ["**Root cause:**", "", fenced_block(description), ""]
    else:
        lines.append(f"**Root cause:** {NOT_AVAILABLE}")
    lines += [
        f"**Remediation:** {_remediation(changes if mr else None)}",
        f"**Merged at:** {merged_at or NOT_AVAILABLE}",
        f"**Minutes from issue to merge:** {_minutes(issue.get('created_at'), merged_at)}",
        f"**Pipeline of the merge commit:** {status or NOT_AVAILABLE}",
    ]
    return "\n".join(lines) + "\n"


def render(blocks: Sequence[str]) -> str:
    """The whole file: a title, then the blocks in the order given."""
    head = (
        f"{TITLE}\n\nGenerated from the GitLab API by `scripts/telemetry_report.py`. "
        f"One block per issue labelled `{LABEL}`; a field with no source says "
        f"`{NOT_AVAILABLE}`.\n"
    )
    if not blocks:
        return f"{head}\nNo self-healing event found.\n"
    return head + "\n" + "\n".join(blocks)


def _closes(issue_iid: int, mr: Mapping[str, Any]) -> bool:
    listed = {c.get("iid") for c in mr.get("closes_issues") or []}
    pattern = rf"\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)\s+#{issue_iid}\b"
    return issue_iid in listed or bool(re.search(pattern, mr.get("description") or "", re.I))


def find_repair_mr(issue_iid: int, mrs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """The merge request that closes the issue; a merged one is preferred to an open one."""
    closing = [m for m in mrs if _closes(issue_iid, m)]
    merged = [m for m in closing if m.get("merged_at")]
    chosen = merged or closing
    return chosen[0] if chosen else None


def _pages(get_json: GetJson, url: str) -> list[Any]:
    sep = "&" if "?" in url else "?"
    rows: list[Any] = []
    for page in range(1, MAX_PAGES + 1):
        chunk = get_json(f"{url}{sep}per_page={PAGE_SIZE}&page={page}")
        rows += chunk
        if len(chunk) < PAGE_SIZE:
            break
    return rows


def _candidates(get_json: GetJson, base: str, iid: int) -> list[Mapping[str, Any]]:
    """Merge requests GitLab says close the issue, then those that only mention it."""
    closing = [
        {**m, "closes_issues": [{"iid": iid}]}
        for m in _pages(get_json, f"{base}/issues/{iid}/closed_by")
    ]
    return closing + _pages(get_json, f"{base}/issues/{iid}/related_merge_requests")


def _block_for(get_json: GetJson, base: str, issue: Mapping[str, Any]) -> str:
    mr = find_repair_mr(int(issue["iid"]), _candidates(get_json, base, int(issue["iid"])))
    if mr is None:
        return build_block(issue, None, None, None)
    changes = _pages(get_json, f"{base}/merge_requests/{mr['iid']}/diffs")
    sha = mr.get("merge_commit_sha")
    pipelines = _pages(get_json, f"{base}/pipelines?sha={sha}") if sha else []
    pipeline = max(pipelines, key=lambda p: p["id"]) if pipelines else None
    return build_block(issue, mr, changes, pipeline)


def collect_blocks(get_json: GetJson, api_url: str, project: str) -> list[str]:
    """Read the labelled issues of the project and build one block for each, oldest first."""
    base = f"{api_url.rstrip('/')}/projects/{urllib.parse.quote(project, safe='')}"
    issues = _pages(
        get_json,
        f"{base}/issues?labels={urllib.parse.quote(LABEL)}&state=all&order_by=created_at&sort=asc",
    )
    return [_block_for(get_json, base, issue) for issue in issues]


def _http_json(url: str) -> Any:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:  # noqa: S310
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise FactsError(f"GitLab refused the request: HTTP {error.code}") from None
    except urllib.error.URLError as error:
        raise FactsError(f"GitLab did not answer: {error.reason}") from None


def main(argv: Sequence[str] | None = None, get_json: GetJson | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the self-healing telemetry report.")
    parser.add_argument("--project", required=True, help="project id or path (public project)")
    parser.add_argument("--out", default="build/AFAW_TELEMETRY.md", type=Path)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    args = parser.parse_args(argv)
    try:
        blocks = collect_blocks(get_json or _http_json, args.api_url, args.project)
    except (FactsError, KeyError, ValueError) as error:
        print(f"telemetry_report: could not read the API: {error}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(blocks), encoding="utf-8")
    print(f"wrote {args.out} ({len(blocks)} blocks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
