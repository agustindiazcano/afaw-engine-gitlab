"""WEAK backup control: fail a change to a human-only file unless a human made it.

This job lives in .gitlab-ci.yml, so the same merge request can edit it away. It enforces
nothing on its own; it makes an accidental or careless automated change visible and red. The
strong controls (a pipeline execution policy in a separate project, or CODEOWNERS with required
approval) are deferred, see PENDING.md.

Human-only files (AGENTS.md section 18.10): .gitlab-ci.yml, AGENTS.md,
state/equivalent_mutants.json, deploy/, and the mutation and gate settings in state/config.json.

"Non-human" is deterministic. The merge request author id and the pipeline user (the pusher)
are the authoritative signals. GitLab answers GET /users/:id only to signed-in users, so each
is looked up by username with GET /users?username=...&humans=true, which leaves out bots and
service accounts: a user that comes back empty, or whose id is in AFAW_BOT_USER_IDS
(comma-separated, a group-level CI variable), is non-human. Commit author names and
emails are forgeable: they only add a warning, never decide.

Run in CI: python -m scripts.human_only_files --base origin/main
Exit codes: 0 ok, 1 a non-human changed a human-only file, 2 could not decide (fails closed).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import quote

from scripts.check_task_delta import changed_files

HUMAN_ONLY_PATHS = (".gitlab-ci.yml", "AGENTS.md", "state/equivalent_mutants.json")
HUMAN_ONLY_PREFIXES = ("deploy/",)
CONFIG_PATH = "state/config.json"
CONFIG_KEYS = ("mutation_critical_paths", "mutation_min_score")
TIMEOUT = 30


def protected_changes(
    changed: list[str], old_config: dict[str, Any], new_config: dict[str, Any]
) -> list[str]:
    """The changed human-only files; state/config.json counts only when a gate key changed."""
    hits = [p for p in changed if p in HUMAN_ONLY_PATHS or p.startswith(HUMAN_ONLY_PREFIXES)]
    if CONFIG_PATH in changed:
        keys = [k for k in CONFIG_KEYS if old_config.get(k) != new_config.get(k)]
        if keys:
            hits.append(f"{CONFIG_PATH} ({', '.join(keys)})")
    return hits


def is_human(found: list[dict[str, Any]], bot_ids: set[int]) -> bool:
    """Human when the humans-only lookup returned the user and its id is not a listed bot."""
    return bool(found) and found[0].get("id") not in bot_ids


def commit_warnings(identities: list[str]) -> list[str]:
    """Warnings for commit identities that look automated; they never decide anything."""
    return [
        f"commit identity looks automated (forgeable, warning only): {who}"
        for who in identities
        if "bot" in who.lower()
    ]


def fetch_json(url: str, token: str | None) -> Any:
    """GET a GitLab API URL as JSON, with the job token when there is one."""
    request = urllib.request.Request(url, headers={"JOB-TOKEN": token} if token else {})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def config_at(base: str, root: Path) -> dict[str, Any]:
    """state/config.json as it is on the merge base (empty when it did not exist)."""
    shown = subprocess.run(
        ["git", "show", f"{base}:{CONFIG_PATH}"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT,
    )
    data: dict[str, Any] = json.loads(shown.stdout) if shown.returncode == 0 else {}
    return data


def commit_identities(base: str, root: Path) -> list[str]:
    """Author identities of the commits on the branch since the base."""
    shown = subprocess.run(
        ["git", "log", f"{base}..HEAD", "--format=%an <%ae>"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT,
    )
    return sorted(set(shown.stdout.splitlines()))


def _bot_ids() -> set[int]:
    raw = os.environ.get("AFAW_BOT_USER_IDS", "")
    return {int(part) for part in raw.replace(" ", "").split(",") if part}


def main(argv: list[str] | None = None) -> int:
    """Check who changed the human-only files of the branch."""
    parser = argparse.ArgumentParser(description="Weak backup control for human-only files.")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--base", required=True, help="git ref to compare with, e.g. origin/main")
    args = parser.parse_args(argv)
    root = Path(args.root)
    new_config = json.loads((root / CONFIG_PATH).read_text(encoding="utf-8"))
    hits = protected_changes(
        changed_files(args.base, root), config_at(args.base, root), new_config
    )
    if not hits:
        sys.stdout.write("No human-only file changed; nothing to check.\n")
        return 0
    sys.stdout.write(
        "WEAK backup control: this job can be edited away by the same merge request, so it "
        "enforces nothing on its own. Human-only files changed:\n"
        + "".join(f"  - {hit}\n" for hit in hits)
    )
    for warning in commit_warnings(commit_identities(args.base, root)):
        sys.stdout.write(f"WARNING: {warning}\n")
    api, project = os.environ.get("CI_API_V4_URL"), os.environ.get("CI_PROJECT_ID")
    token, iid = os.environ.get("CI_JOB_TOKEN"), os.environ.get("CI_MERGE_REQUEST_IID")
    if not api or not project:
        sys.stderr.write("ERROR: CI_API_V4_URL and CI_PROJECT_ID are required to decide\n")
        return 2
    try:
        names = {"pusher": os.environ["GITLAB_USER_LOGIN"]}
        if iid:
            merge_request = fetch_json(f"{api}/projects/{project}/merge_requests/{iid}", token)
            names["merge request author"] = str(merge_request["author"]["username"])
        found = {
            role: fetch_json(f"{api}/users?username={quote(name)}&humans=true", token)
            for role, name in names.items()
        }
    except (KeyError, ValueError, TypeError, urllib.error.URLError) as exc:
        sys.stderr.write(f"ERROR: could not identify who made this change ({exc!r})\n")
        return 2
    bot_ids = _bot_ids()
    failed = [role for role, users in found.items() if not is_human(users, bot_ids)]
    for role in failed:
        sys.stderr.write(f"PROBLEM: the {role} is not human and changed a human-only file\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
