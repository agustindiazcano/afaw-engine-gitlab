"""The configure stage: validate the project's settings and the CI variables it depends on.

state/config.json is checked against its JSON Schema. Required CI variables must exist; only
their names and whether they are set are printed, never their values. Optional variables are
reported so a missing one is visible. The Google Cloud variables are protected, so they exist
only on protected refs (the deploy runs on main): they are required there and merely listed
elsewhere, where their absence is expected.

The list of required names is itself validated: a name that is duplicated, empty or only
whitespace is a defect in this script, so it fails before any variable is checked. The message
lists the offending names, never any variable value.

After the per-variable lines one summary line, ``variables: N of M set``, counts the variables
checked on this ref (required and optional; "not checked" ones are left out), names only.

Run in CI: python -m scripts.check_ci_config
Exit codes: 0 ok, 1 a required variable is missing, 2 the config is invalid, 3 the declared list
of required names has a duplicated, empty or whitespace-only name.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from scripts.project_config import load_config
from scripts.state_common import StateError

REQUIRED = ("CI_REGISTRY_IMAGE", "CI_DEFAULT_BRANCH")
PROTECTED_REQUIRED = (
    "GCP_PROJECT_ID",
    "GCP_REGION",
    "GCP_WORKLOAD_IDENTITY_PROVIDER",
    "GCP_DEPLOYER_SERVICE_ACCOUNT",
    "GCP_ARTIFACT_REPOSITORY",
    "GCP_SERVICE_NAME",
    "GCP_SERVICE_URL",
)
OPTIONAL = {"AFAW_BOT_USER_IDS": "group-level variable filled in task 011"}


def invalid_names(names: Sequence[str]) -> list[str]:
    """Describe each duplicated, empty or whitespace-only name in ``names``; names only."""
    problems = [f"empty or whitespace-only name: {name!r}" for name in names if not name.strip()]
    counts = Counter(name for name in names if name.strip())
    problems += [f"duplicated name: {name}" for name, count in counts.items() if count > 1]
    return problems


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    """Validate state/config.json and report the CI variables by name only."""
    parser = argparse.ArgumentParser(description="Validate the project configuration for CI.")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ
    try:
        load_config(Path(args.root))
    except StateError as exc:
        sys.stderr.write(f"ERROR: state/config.json is invalid: {exc}\n")
        return 2
    sys.stdout.write("state/config.json: valid against its schema\n")
    problems = invalid_names(REQUIRED + PROTECTED_REQUIRED)
    if problems:
        for problem in problems:
            sys.stderr.write(f"ERROR: required variable list: {problem}\n")
        return 3
    protected = env.get("CI_COMMIT_REF_PROTECTED") == "true"
    names = REQUIRED + (PROTECTED_REQUIRED if protected else ())
    missing = [name for name in names if not env.get(name)]
    if not protected:
        for name in PROTECTED_REQUIRED:
            sys.stdout.write(f"{name}: not checked (protected variable, ref is not protected)\n")
    for name in names:
        if name in missing:
            sys.stderr.write(f"PROBLEM: {name}: MISSING\n")
        else:
            sys.stdout.write(f"{name}: set\n")
    for name, note in OPTIONAL.items():
        state = "set" if env.get(name) else f"not set (optional, {note})"
        sys.stdout.write(f"{name}: {state}\n")
    checked = [*names, *OPTIONAL]
    set_count = sum(1 for name in checked if env.get(name))
    sys.stdout.write(f"variables: {set_count} of {len(checked)} set\n")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
