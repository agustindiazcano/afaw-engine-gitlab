#!/usr/bin/env python3
"""The mutation engine of the CI job: run mutmut on the required files and write the results.

It finds the required files of the branch (scripts.mutation_targets), writes a mutmut
configuration for them, runs ``python -m mutmut run`` with a timeout and converts what mutmut
left in ``mutants/`` into the results file that scripts.mutation_ci and scripts.mutation_gate
read. With no required file it runs nothing and says so; scripts.mutation_ci then reports the
same. It needs a system with fork support (mutmut 3 does not run on native Windows).

Only one source directory and one test selection are supported: that is what was run and read on
the CI runner (mutmut 3.8.0, 2026-10-25). More is refused, not guessed.

Run in CI: python -m scripts.mutation_engine --base origin/main --out build/mutation.json
Exit codes: 0 results written or nothing to mutate, 2 could not run (nothing is written).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path, PurePosixPath

from scripts import mutmut_results
from scripts.check_task_delta import changed_files
from scripts.mutation_targets import classify
from scripts.project_config import load_config
from scripts.state_common import StateError

DEFAULT_TESTS = "tests/web"
DEFAULT_TIMEOUT = 900


class EngineError(RuntimeError):
    """mutmut could not be configured or run."""


def mutmut_config(required: list[str], tests: str) -> str:
    """The ``setup.cfg`` text that makes mutmut mutate only ``required`` and run ``tests``."""
    directories = {PurePosixPath(path).parent.as_posix() for path in required}
    if len(directories) != 1:
        raise EngineError(
            f"required files in {len(directories)} directories: only one directory is "
            "supported, more is not verified with mutmut"
        )
    # mutmut 3.8.0 reads a list from one item per line; a comma-separated line is one pattern.
    only_mutate = "\n  ".join(required)
    return (
        "[mutmut]\n"
        f"source_paths={directories.pop()}/\n"
        f"only_mutate={only_mutate}\n"
        f"pytest_add_cli_args_test_selection={tests}\n"
    )


def run_mutmut(root: Path, required: list[str], tests: str, timeout: int) -> None:
    """Write the configuration, run mutmut in ``root`` and leave its results in ``mutants/``."""
    config = root / "setup.cfg"
    if config.exists():
        raise EngineError("setup.cfg already exists; it would be overwritten")
    config.write_text(mutmut_config(required, tests), encoding="utf-8")
    try:
        subprocess.run(
            [sys.executable, "-m", "mutmut", "run"],
            cwd=root,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise EngineError(f"mutmut timed out after {timeout} seconds") from None
    finally:
        config.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """Mutate the required files of the branch and write the gate's results file."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--base", required=True, help="git ref to compare with, e.g. origin/main")
    parser.add_argument("--out", type=Path, required=True, help="results file for the gate")
    parser.add_argument("--tests", default=DEFAULT_TESTS, help="tests mutmut runs per mutant")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="seconds for mutmut")
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        config = load_config(root)
        required = [str(p) for p in classify(changed_files(args.base, root), config)["required"]]
        if not required:
            sys.stdout.write("NO MANDATORY FILES: nothing to mutate.\n")
            return 0
        run_mutmut(root, required, args.tests, args.timeout)
        results = mutmut_results.convert(root / "mutants")
    except (StateError, EngineError, mutmut_results.MutmutError) as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    mutmut_results.write(results, args.out)
    sys.stdout.write(f"wrote the results of {len(results['files'])} file(s) to {args.out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
