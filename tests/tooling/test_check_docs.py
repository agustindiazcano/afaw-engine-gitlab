"""Tests for scripts.check_docs, run in-process so that its entry point is measured."""

from __future__ import annotations

import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_docs

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

ADR = """---
status: accepted
date: 2026-09-24
tags: [db]
---
# Money in cents

## Context
c
## Decision
d
## Alternatives considered
a
## Consequences
e
"""

GOTCHA = """---
status: active
date: 2026-10-01
---
# A trap

## Symptom
s
## What to do
w
"""


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_tracked_files_lists_only_tracked_paths(repo: Path) -> None:
    write(repo, "docs/a.md", "# A\n")
    write(repo, "docs/untracked.md", "# U\n")
    git(repo, "add", "docs/a.md")
    assert check_docs.tracked_files(repo) == {"docs/a.md"}


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_tracked_files_outside_a_repository_raises(tmp_path: Path) -> None:
    with pytest.raises(subprocess.CalledProcessError):
        check_docs.tracked_files(tmp_path)


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_valid_adr_and_gotcha_have_no_errors(tmp_path: Path) -> None:
    write(tmp_path, "docs/adr/0001-money-in-cents.md", ADR)
    write(tmp_path, "docs/gotchas/0001-a-trap.md", GOTCHA)
    existing = {"docs/adr/0001-money-in-cents.md", "docs/gotchas/0001-a-trap.md"}
    assert check_docs.check(tmp_path, existing) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_invalid_adr_is_reported_with_its_path(tmp_path: Path) -> None:
    write(tmp_path, "docs/adr/0001-money-in-cents.md", ADR.replace("accepted", "maybe"))
    errors = check_docs.check(tmp_path, {"docs/adr/0001-money-in-cents.md"})
    assert errors == ["docs/adr/0001-money-in-cents.md: invalid status: 'maybe'"]


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_bad_file_name_is_reported(tmp_path: Path) -> None:
    write(tmp_path, "docs/gotchas/Trap.md", GOTCHA)
    errors = check_docs.check(tmp_path, {"docs/gotchas/Trap.md"})
    assert "docs/gotchas/Trap.md: file name must be NNNN-slug.md (lowercase, hyphens)" in errors


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_nested_and_non_markdown_files_are_not_parsed_as_knowledge(tmp_path: Path) -> None:
    # Only files directly inside docs/adr or docs/gotchas are ADRs or gotchas.
    write(tmp_path, "docs/adr/sub/notes.md", "no front matter\n")
    write(tmp_path, "docs/adr/0002-data.json", "{}")
    existing = {"docs/adr/sub/notes.md", "docs/adr/0002-data.json"}
    assert check_docs.check(tmp_path, existing) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_duplicate_ids_are_reported(tmp_path: Path) -> None:
    write(tmp_path, "docs/adr/0001-first.md", ADR)
    write(tmp_path, "docs/adr/0001-second.md", ADR)
    errors = check_docs.check(tmp_path, {"docs/adr/0001-first.md", "docs/adr/0001-second.md"})
    assert errors == [
        "docs/adr/0001-second.md: duplicate adr id 0001 (also docs/adr/0001-first.md)"
    ]


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
@pytest.mark.parametrize("top", ["README.md", "AGENTS.md", "CLAUDE.md"])
def test_broken_link_in_a_top_level_document_is_reported(tmp_path: Path, top: str) -> None:
    write(tmp_path, top, "See [guide](docs/missing.md).\n")
    assert check_docs.check(tmp_path, {top}) == [f"{top}: broken link: docs/missing.md"]


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_broken_link_under_docs_is_reported(tmp_path: Path) -> None:
    write(tmp_path, "docs/guide.md", "[x](other.md) and [y](#anchor)\n")
    assert check_docs.check(tmp_path, {"docs/guide.md"}) == ["docs/guide.md: broken link: other.md"]


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_link_to_a_tracked_file_resolves(tmp_path: Path) -> None:
    write(tmp_path, "docs/guide.md", "[x](other.md#section)\n")
    write(tmp_path, "docs/other.md", "# Other\n")
    assert check_docs.check(tmp_path, {"docs/guide.md", "docs/other.md"}) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_markdown_outside_docs_and_top_level_is_not_link_checked(tmp_path: Path) -> None:
    write(tmp_path, "notes/todo.md", "[x](missing.md)\n")
    assert check_docs.check(tmp_path, {"notes/todo.md"}) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_main_returns_zero_and_prints_nothing_when_valid(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(repo, "docs/adr/0001-money-in-cents.md", ADR)
    git(repo, "add", ".")
    assert check_docs.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_main_returns_one_and_prints_every_error_to_stderr(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(repo, "docs/adr/0001-money-in-cents.md", ADR + "\n[gone](../gone.md)\n")
    write(repo, "README.md", "[nope](nope.md)\n")
    git(repo, "add", ".")
    assert check_docs.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == [
        "README.md: broken link: nope.md",
        "docs/adr/0001-money-in-cents.md: broken link: ../gone.md",
    ]


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_main_ignores_files_that_are_not_tracked(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(repo, "docs/adr/0001-bad.md", "no front matter\n")
    assert check_docs.main() == 0
    assert capsys.readouterr().err == ""


@pytest.mark.characterization(
    reason="the code already did this; the test pins check_docs so a change is noticed"
)
def test_running_the_module_exits_with_the_status_of_main(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    write(repo, "README.md", "[nope](nope.md)\n")
    git(repo, "add", ".")
    monkeypatch.delitem(sys.modules, "scripts.check_docs")
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("scripts.check_docs", run_name="__main__")
    assert exc.value.code == 1
    assert capsys.readouterr().err == "README.md: broken link: nope.md\n"
