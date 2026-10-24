"""Tests for scripts.check_ci_config: the configure stage checks settings, never prints values."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts import check_ci_config

if TYPE_CHECKING:
    from tests.tooling.conftest import Project

REQUIRED = {"CI_REGISTRY_IMAGE": "registry.example/x", "CI_DEFAULT_BRANCH": "main"}


def _run(project: Project, env: dict[str, str]) -> int:
    return check_ci_config.main(["--root", str(project.root)], environ=env)


def test_valid_config_and_required_variables_pass(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {"mutation_min_score": 80})
    assert _run(project, REQUIRED) == 0
    out = capsys.readouterr().out
    assert "CI_REGISTRY_IMAGE: set" in out and "registry.example" not in out


def test_missing_required_variable_fails(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {})
    assert _run(project, {"CI_DEFAULT_BRANCH": "main"}) == 1
    assert "CI_REGISTRY_IMAGE: MISSING" in capsys.readouterr().err


def test_invalid_config_fails(project: Project, capsys: pytest.CaptureFixture[str]) -> None:
    project.write("state/config.json", {"mutation_min_score": -5})
    assert _run(project, REQUIRED) == 2
    assert "mutation_min_score" in capsys.readouterr().err


def test_optional_variable_is_reported_not_required(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {})
    assert _run(project, REQUIRED) == 0
    assert "AFAW_BOT_USER_IDS: not set (optional" in capsys.readouterr().out
