"""Build the Markdown description of a release from merged merge requests.

``render`` is a pure function: it takes the merge requests (dicts shaped like the GitLab API
merge request, with ``iid``, ``title`` and ``author.username``) and a tag, and returns Markdown.
The CLI reads them from a JSON file and writes the Markdown to stdout. It makes no network call
and writes no file.

Run: python -m scripts.release_notes --merge-requests mrs.json [--tag v1.0.0]
Exit codes: 0 ok, 2 could not run (details on stderr).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_TAG = "unreleased"


def _bullet(merge_request: dict[str, Any]) -> str:
    """One ``- !IID title (author)`` line; the title is kept verbatim."""
    author = merge_request["author"]["username"]
    return f"- !{merge_request['iid']} {merge_request['title']} ({author})"


def render(merge_requests: list[dict[str, Any]], tag: str) -> str:
    """Return the release notes: a heading, one bullet per merge request by IID, the count."""
    ordered = sorted(merge_requests, key=lambda merge_request: int(merge_request["iid"]))
    count = len(ordered)
    noun = "merge request" if count == 1 else "merge requests"
    lines = [f"## {tag}", ""]
    if ordered:
        lines += [_bullet(merge_request) for merge_request in ordered]
        lines.append("")
    lines.append(f"{count} {noun}")
    return "\n".join(lines) + "\n"


def _load(path: Path) -> list[dict[str, Any]]:
    """Read a JSON list of merge requests; raise ValueError if the file is not usable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list of merge requests")
    return data


def main(argv: list[str] | None = None) -> int:
    """Print the release notes of the merge requests in a JSON file."""
    parser = argparse.ArgumentParser(description="Render release notes from merge requests.")
    parser.add_argument("--merge-requests", required=True, help="JSON file with a list of MRs")
    parser.add_argument("--tag", default=DEFAULT_TAG, help="release tag (default: unreleased)")
    args = parser.parse_args(argv)
    try:
        text = render(_load(Path(args.merge_requests)), args.tag)
    except (ValueError, KeyError, TypeError) as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
