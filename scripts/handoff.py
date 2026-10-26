#!/usr/bin/env python3
"""Write the hand-over file for the next session (ADR 0011).

The file holds facts the script reads itself, so they do not depend on anyone's memory:

* the commit and branch it was written at, and the commit of ``origin/main`` at that moment (read
  with ``git``, each call with a timeout);
* the open merge requests, the open issues and the last pipelines of ``main`` (the public GitLab
  REST API v4, no token);
* the open items of ``PENDING.md`` (lines that start with ``- [ ]``);

followed by the free text of ``--note`` under "What is done, what is next". The session-start hook
prints the file and says when ``main`` has moved since the commit it records.

The text is checked by ``refuse_secrets`` before anything is written; a match writes nothing.

Usage: python -m scripts.handoff --note "..." [--out state/handoff/HANDOFF.md] [--project ID]
Exit codes: 0 written, 2 a secret was found or a fact could not be read (nothing is written).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.afaw_state.facts import FactsError, http_get_json

API = "https://gitlab.com/api/v4"
DEFAULT_PROJECT = "88052530"
DEFAULT_OUT = "state/handoff/HANDOFF.md"
GIT_TIMEOUT_SECONDS = 30
PAGE_SIZE = 100
PIPELINE_COUNT = 5

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GitLab personal access token (glpat-)", re.compile(r"glpat-[A-Za-z0-9_-]{8,}")),
    ("GitHub token (ghp_)", re.compile(r"ghp_[A-Za-z0-9]{16,}")),
    ("AWS access key id (AKIA)", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "long base64 or hex run after token or secret",
        re.compile(r"(?i)(?:token|secret)\b[^\n]{0,20}?(?=[A-Za-z0-9+/=_-]*\d)[A-Za-z0-9+/=_-]{32,}"),
    ),
)


class HandoffError(Exception):
    """A fact for the handoff file could not be read."""


def refuse_secrets(text: str) -> None:
    """Raise ValueError when ``text`` matches a token pattern; the message names the pattern."""
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"refusing to write the handoff: text matches {name}")


def parse_pending(text: str) -> list[str]:
    """The open items of PENDING.md: lines that start with ``- [ ]``, without trailing blanks."""
    return [line.rstrip() for line in text.splitlines() if line.startswith("- [ ]")]


def _section(title: str, lines: Sequence[str]) -> str:
    body = "\n".join(lines) if lines else "None."
    return f"## {title}\n\n{body}\n"


def build(facts: Mapping[str, Any], note: str) -> str:
    """The handoff file as Markdown: facts first, then ``note`` as the last section."""
    written = [
        f"- Commit: `{facts['commit']}`",
        f"- Branch: `{facts['branch']}`",
        f"- Main: `{facts['main_commit']}`",
    ]
    merge_requests = [
        f"- !{m['iid']} {m['title']} ({m['web_url']})" for m in facts["merge_requests"]
    ]
    issues = [f"- #{i['iid']} {i['title']} ({i['web_url']})" for i in facts["issues"]]
    pipelines = [f"- {p['id']}: {p['status']}" for p in facts["pipelines"]]
    parts = [
        "# Handoff\n",
        _section("Written at", written),
        _section("Open merge requests", merge_requests),
        _section("Open issues", issues),
        _section("Last pipelines of main", pipelines),
        _section("Open items of PENDING.md", list(facts["pending"])),
        _section("What is done, what is next", [note.strip()]),
    ]
    return "\n".join(parts)


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise HandoffError(f"git {' '.join(args)} failed: {exc}") from exc
    return result.stdout.strip()


def git_facts(root: Path) -> dict[str, str]:
    """The commit and branch of the working tree and the commit of ``origin/main``."""
    return {
        "commit": _git(root, "rev-parse", "HEAD"),
        "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "main_commit": _git(root, "rev-parse", "origin/main"),
    }


def _list(get: Callable[[str], Any], url: str) -> list[Any]:
    items: list[Any] = get(url)
    if len(items) >= PAGE_SIZE:
        raise HandoffError(f"{url.split('?')[0]}: {PAGE_SIZE} or more items; the list is partial")
    return items


def gitlab_facts(get: Callable[[str], Any], project: str) -> dict[str, Any]:
    """Open merge requests, open issues and the last pipelines of ``main`` from the public API."""
    base = f"{API}/projects/{urllib.parse.quote(project, safe='')}"
    opened = urllib.parse.urlencode({"state": "opened", "per_page": PAGE_SIZE})
    merge_requests = _list(get, f"{base}/merge_requests?{opened}")
    issues = _list(get, f"{base}/issues?{opened}")
    latest = urllib.parse.urlencode({"ref": "main", "per_page": PIPELINE_COUNT})
    pipelines = get(f"{base}/pipelines?{latest}")
    return {
        "merge_requests": [
            {"iid": m["iid"], "title": m["title"], "web_url": m["web_url"]}
            for m in merge_requests
        ],
        "issues": [
            {"iid": i["iid"], "title": i["title"], "web_url": i["web_url"]} for i in issues
        ],
        "pipelines": [{"id": p["id"], "status": p["status"]} for p in pipelines],
    }


def gather(root: Path, project: str) -> dict[str, Any]:
    """Every fact of the handoff file: git, the GitLab API and PENDING.md."""
    facts: dict[str, Any] = dict(git_facts(root))
    try:
        facts.update(gitlab_facts(lambda url: http_get_json(url, {}), project))
    except (FactsError, OSError, ValueError) as exc:
        raise HandoffError(f"GitLab API: {exc}") from exc
    pending = root / "PENDING.md"
    text = pending.read_text(encoding="utf-8") if pending.is_file() else ""
    facts["pending"] = parse_pending(text)
    return facts


def main(argv: list[str] | None = None) -> int:
    """Gather the facts, refuse secrets, write the file."""
    parser = argparse.ArgumentParser(description="Write the hand-over file for the next session.")
    parser.add_argument("--note", required=True, help="what is done and what is next")
    parser.add_argument("--out", type=Path, default=Path(DEFAULT_OUT))
    parser.add_argument("--project", default=os.environ.get("CI_PROJECT_ID", DEFAULT_PROJECT))
    args = parser.parse_args(argv)
    try:
        refuse_secrets(args.note)
        text = build(gather(Path.cwd(), args.project), args.note)
        refuse_secrets(text)
    except (ValueError, HandoffError) as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(f"wrote {args.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
