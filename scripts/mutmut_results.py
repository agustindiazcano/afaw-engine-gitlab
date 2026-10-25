#!/usr/bin/env python3
"""Turn the results of mutmut 3 into the results file of the mutation gate.

mutmut writes, for every source file it mutated, ``mutants/<path>.meta``: a JSON object whose
``exit_code_by_key`` maps each mutant to the exit code of the test run on it. On 2026-10-25 the
CI runner (mutmut 3.8.0) wrote 1 for a mutant the tests caught and 0 for one they did not, and
``mutmut results --all`` agreed. Any other code, or no code, is not a result this script knows,
so it fails instead of guessing: a gate must not score what it cannot read.

A file with no mutants (mutmut mutates functions only) is left out; the gate then says that a
required file has no results.

Usage:
    python -m scripts.mutmut_results --mutants mutants --out build/mutation.json
Exit codes: 0 written, 2 could not convert (nothing is written).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

KILLED_EXIT_CODE = 1
SURVIVED_EXIT_CODE = 0


class MutmutError(RuntimeError):
    """The mutmut output cannot be turned into results."""


def _statuses(meta_path: Path) -> list[dict[str, str]]:
    try:
        codes = json.loads(meta_path.read_text(encoding="utf-8"))["exit_code_by_key"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise MutmutError(f"{meta_path}: no exit_code_by_key ({exc!r})") from None
    mutants = []
    for key, code in codes.items():
        if code == KILLED_EXIT_CODE:
            status = "killed"
        elif code == SURVIVED_EXIT_CODE:
            status = "survived"
        else:
            raise MutmutError(f"{meta_path}: mutant {key} has exit code {code!r}, not 0 or 1")
        mutants.append({"id": key, "status": status})
    return mutants


def convert(mutants_dir: Path) -> dict[str, Any]:
    """The gate's ``{"files": {path: {"mutants": [...]}}}`` for a mutmut ``mutants`` directory."""
    if not mutants_dir.is_dir():
        raise MutmutError(f"{mutants_dir} does not exist")
    metas = sorted(mutants_dir.rglob("*.meta"))
    if not metas:
        raise MutmutError(f"no .meta files under {mutants_dir}")
    files: dict[str, Any] = {}
    for meta in metas:
        mutants = _statuses(meta)
        if mutants:
            source = meta.relative_to(mutants_dir).as_posix().removesuffix(".meta")
            files[source] = {"mutants": mutants}
    return {"files": files}


def write(results: dict[str, Any], out: Path) -> None:
    """Write ``results`` as the gate's JSON file."""
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Write the converted results; exit 2 and write nothing if they cannot be read."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mutants", type=Path, default=Path("mutants"), help="mutmut directory")
    parser.add_argument("--out", type=Path, required=True, help="results file for the gate")
    args = parser.parse_args(argv)
    try:
        results = convert(args.mutants)
    except MutmutError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write(results, args.out)
    sys.stdout.write(f"wrote the results of {len(results['files'])} file(s) to {args.out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
