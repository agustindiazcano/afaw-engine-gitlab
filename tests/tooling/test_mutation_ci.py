"""Tests for scripts.mutation_ci: the CI wrapper never reports an empty pass."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from scripts import mutation_ci

if TYPE_CHECKING:
    from tests.tooling.conftest import Project

CRITICAL = "src/back/domain/fees.py"


def _run(project: Project, monkeypatch: pytest.MonkeyPatch, changed: list[str]) -> int:
    monkeypatch.setattr(mutation_ci, "changed_files", lambda base, root: changed)
    project.write("state/config.json", {"mutation_critical_paths": ["src/back/domain/"]})
    args = ["--root", str(project.root), "--base", "origin/main"]
    return mutation_ci.main([*args, "--results", str(project.root / "mutation.json")])


def test_no_mandatory_files_says_so_explicitly(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(project, monkeypatch, ["docs/a.md", "src/back/other.py"]) == 0
    assert "NO MANDATORY FILES" in capsys.readouterr().out


def test_mandatory_file_without_engine_results_fails(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(project, monkeypatch, [CRITICAL]) == 1
    assert "no mutation engine results" in capsys.readouterr().err


def test_mandatory_file_with_results_is_gated(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mutants = [{"id": f"m{i}", "status": "killed"} for i in range(10)]
    project.write("mutation.json", {"files": {CRITICAL: {"mutants": mutants}}})
    assert _run(project, monkeypatch, [CRITICAL]) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True


def test_mandatory_file_below_the_minimum_fails(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    mutants = [{"id": f"m{i}", "status": "survived"} for i in range(10)]
    project.write("mutation.json", {"files": {CRITICAL: {"mutants": mutants}}})
    assert _run(project, monkeypatch, [CRITICAL]) == 1
