"""Pick the next task to work on, in code, from the derived pending view.

The choice is a pure function of ``build/state/pending.json`` (ADR 0010): the same view gives the
same task, and no credits are spent. An agent only writes the issue text for the selected task.

Usage:
    python -m scripts.build_state --ref gitlab/main
    python -m scripts.orchestrator [--pending build/state/pending.json]
    python -m scripts.orchestrator --create --project 88052530   (needs a token in the environment)
Prints ``{"selected": <task or null>, "reason": <text>}`` and exits 0; exits 2 when the view
is missing or when ``--create`` has no token. With ``--create`` the issue text comes from a fixed
template (no model writes it), the issue is assigned to the Developer Flow account, and a task that
already has an open issue is not filed twice.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.request_fix import FLOW_USERNAME, Api

DEFAULT_PENDING = Path("build/state/pending.json")
LABEL = "afaw-orchestrator"
API_URL = "https://gitlab.com/api/v4"
ELIGIBLE_STATUS = ("pending", "backlog")


def _open_ids(tasks: Sequence[Mapping[str, Any]]) -> set[str]:
    """Ids of tasks that are not finished: the pending view lists only those that are open."""
    return {str(t["id"]) for t in tasks}


def select_next(tasks: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """The eligible task with the lowest priority number, then difficulty, then id."""
    open_ids = _open_ids(tasks)
    eligible = [
        t
        for t in tasks
        if t.get("status") in ELIGIBLE_STATUS
        and t.get("owner") == "agent"
        and not any(str(b) in open_ids for b in t.get("blocked_by", []))
    ]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda t: (t.get("priority", 5), t.get("difficulty_estimate", 5), str(t["id"])),
    )


def marker(task_id: str) -> str:
    """The hidden comment that ties an issue to the task it was filed for."""
    return f"<!-- afaw-orchestrator task={task_id} -->"


def issue_title(task: Mapping[str, Any]) -> str:
    """Conventional-commit style title: ``feat(task_77): <task title>``."""
    return f"feat({task['id']}): {task.get('title', '')}"


def issue_text(task: Mapping[str, Any]) -> str:
    """Fixed template: which task to do and the rules every session follows."""
    return (
        f"Do {task['id']}: {task.get('title', '')}\n\n"
        f"Role {task.get('role', 'architect')}, priority {task.get('priority')}, "
        f"difficulty {task.get('difficulty_estimate')}. Read `state/tasks/{task['id']}.json` "
        "and `PENDING.md` first. Follow AGENTS.md: strict TDD (commit the failing tests first, "
        "then the code; `python -m scripts.red_check --base origin/main` must pass), use the "
        "task id above, write the task file and the delta, and run "
        "`python -m scripts.check_task_delta --base origin/main --write` after the last code "
        "commit. Do not weaken, skip or delete a test. Do not touch `.gitlab-ci.yml`, "
        "`AGENTS.md`, `CODEOWNERS`, `state/config.json`, `state/equivalent_mutants.json` "
        f"or `deploy/`.\n\n{marker(str(task['id']))}"
    )


def create_issue(api: Any, task: Mapping[str, Any]) -> str:
    """File the issue for the Developer Flow; ``exists`` when the task already has an open one."""
    tag = marker(str(task["id"]))
    if any(tag in str(i.get("description", "")) for i in api.labeled_issues(LABEL)):
        return "exists"
    api.create_issue(issue_title(task), issue_text(task), api.user_id(FLOW_USERNAME), LABEL)
    return "created"


def main(argv: Sequence[str] | None = None) -> int:
    """Read the pending view, print the selection and the reason."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pending", type=Path, default=DEFAULT_PENDING)
    parser.add_argument("--create", action="store_true", help="file the issue for the Flow")
    parser.add_argument("--project", help="GitLab project id (with --create)")
    args = parser.parse_args(argv)
    try:
        tasks = json.loads(args.pending.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: cannot read the pending view {args.pending}: {exc}", file=sys.stderr)
        return 2
    chosen = select_next(tasks)
    if chosen is None:
        out: dict[str, Any] = {"selected": None, "reason": "no eligible task"}
    else:
        reason = (
            f"priority {chosen.get('priority')}, difficulty {chosen.get('difficulty_estimate')}, "
            f"status {chosen.get('status')}, no open blocker"
        )
        out = {"selected": dict(chosen), "reason": reason}
    if args.create and chosen is not None:
        token = os.environ.get("AFAW_MERGE_TOKEN") or os.environ.get("GITLAB_TOKEN")
        if not token or not args.project:
            print("ERROR: --create needs --project and a token in the environment", file=sys.stderr)
            return 2
        out["issue"] = create_issue(Api(API_URL, args.project, token), chosen)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
