"""Pick the next task to work on, in code, from the derived pending view.

The choice is a pure function of ``build/state/pending.json`` (ADR 0010): the same view gives the
same task, and no credits are spent. An agent only writes the issue text for the selected task.

Usage:
    python -m scripts.build_state --ref gitlab/main
    python -m scripts.orchestrator [--pending build/state/pending.json]
Prints ``{"selected": <task or null>, "reason": <text>}`` and exits 0; exits 2 when the view
is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

DEFAULT_PENDING = Path("build/state/pending.json")
ELIGIBLE_STATUS = ("pending", "backlog")


def _open_ids(tasks: Sequence[Mapping[str, Any]]) -> set[str]:
    """Ids of tasks that are not finished: the pending view lists only those that are open."""
    return {str(t["id"]) for t in tasks}


def select_next(tasks: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """The eligible task with the lowest priority number, then difficulty, then id."""
    open_ids = _open_ids(tasks)
    eligible = [
        t for t in tasks
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


def main(argv: Sequence[str] | None = None) -> int:
    """Read the pending view, print the selection and the reason."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pending", type=Path, default=DEFAULT_PENDING)
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
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
