#!/usr/bin/env python3
"""Collect measured facts per task from git and the GitLab or GitHub API.

The forge is chosen by environment and never guessed:
    GitLab: CI_API_V4_URL and CI_PROJECT_ID (both set by GitLab CI; optional GITLAB_TOKEN for a
            private project). The project is public, so CI sends no token.
    GitHub: GITHUB_REPOSITORY=owner/repo, GITHUB_TOKEN with read access to pulls and actions.

Usage:
    python -m scripts.collect_facts --ref HEAD --out build/facts.json

Facts of merged tasks are final, so an existing output file is reused as a cache.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from scripts.afaw_state.facts import FactsError, Git, collect, forge_from_env
from scripts.afaw_state.source import read_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", default="origin/main")
    parser.add_argument("--out", default="build/facts.json", type=Path)
    args = parser.parse_args(argv)

    try:
        forge = forge_from_env(os.environ)
        source = read_source(args.ref)
        cache = json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else {}
        facts = collect(source["tasks"], args.ref, Git(), forge, cache)
    except FactsError as error:
        print(f"collect_facts: {error}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote facts for {len(facts)} tasks to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
