"""CI entry point for the mutation gate: it never reports an empty pass.

With no mandatory file among the changed ones it prints NO MANDATORY FILES and succeeds. With
mandatory files it requires the mutation engine's results (the engine is specific to each
project and is not part of this boilerplate) and delegates to scripts.mutation_gate; a missing
results file fails, because a gate that could not run is not a pass.

Run in CI: python -m scripts.mutation_ci --base origin/main --results build/mutation.json
Exit codes: 0 ok or nothing mandatory, 1 gate failed or no results, 2 could not run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts import mutation_gate
from scripts.check_task_delta import changed_files
from scripts.mutation_targets import classify
from scripts.project_config import load_config
from scripts.state_common import StateError


def main(argv: list[str] | None = None) -> int:
    """Gate the mandatory mutation targets of the branch, or say there are none."""
    parser = argparse.ArgumentParser(description="Mutation gate for CI, never an empty pass.")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--base", required=True, help="git ref to compare with, e.g. origin/main")
    parser.add_argument("--results", required=True, help="the mutation engine's results JSON")
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        config = load_config(root)
        required = classify(changed_files(args.base, root), config)["required"]
    except StateError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    if not required:
        paths = ", ".join(config.mutation_critical_paths) or "none configured"
        sys.stdout.write(
            f"NO MANDATORY FILES: no changed file is under mutation_critical_paths ({paths}); "
            "the mutation gate does not apply to this change.\n"
        )
        return 0
    if not Path(args.results).is_file():
        sys.stderr.write(
            f"PROBLEM: {len(required)} mandatory file(s) changed but there are no mutation "
            f"engine results at {args.results}: {', '.join(required)}\n"
        )
        return 1
    return mutation_gate.main(
        ["--root", str(root), "--results", args.results, "--required", *required]
    )


if __name__ == "__main__":
    raise SystemExit(main())
