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


GCP = {
    "GCP_PROJECT_ID": "p",
    "GCP_REGION": "r",
    "GCP_WORKLOAD_IDENTITY_PROVIDER": "w",
    "GCP_DEPLOYER_SERVICE_ACCOUNT": "d",
    "GCP_ARTIFACT_REPOSITORY": "a",
    "GCP_SERVICE_NAME": "s",
    "GCP_SERVICE_URL": "https://live.example",
}


def test_gcp_variables_are_required_on_protected_refs(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {})
    env = {**REQUIRED, "CI_COMMIT_REF_PROTECTED": "true"}
    assert _run(project, env) == 1
    err = capsys.readouterr().err
    for name in GCP:
        assert f"{name}: MISSING" in err


def test_gcp_variables_pass_on_protected_refs_without_printing_values(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {})
    assert _run(project, {**REQUIRED, **GCP, "CI_COMMIT_REF_PROTECTED": "true"}) == 0
    out = capsys.readouterr().out
    assert "GCP_PROJECT_ID: set" in out and "live.example" not in out


def test_gcp_variables_are_not_demanded_on_unprotected_refs(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    """Protected variables do not exist on branches and merge requests: say so, do not fail."""
    project.write("state/config.json", {})
    assert _run(project, REQUIRED) == 0
    assert "GCP_PROJECT_ID: not checked (protected variable" in capsys.readouterr().out


def _declare(monkeypatch: pytest.MonkeyPatch, required: tuple[str, ...]) -> None:
    monkeypatch.setattr(check_ci_config, "REQUIRED", required)
    monkeypatch.setattr(check_ci_config, "PROTECTED_REQUIRED", ())


@pytest.mark.characterization(reason="a valid list of names already passes; it must stay so")
def test_valid_name_list_passes(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {})
    _declare(monkeypatch, ("CI_REGISTRY_IMAGE", "CI_DEFAULT_BRANCH"))
    assert _run(project, REQUIRED) == 0
    assert "PROBLEM" not in capsys.readouterr().err


def test_duplicated_name_fails_and_is_listed_without_values(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {})
    _declare(monkeypatch, ("CI_REGISTRY_IMAGE", "CI_DEFAULT_BRANCH", "CI_REGISTRY_IMAGE"))
    assert _run(project, REQUIRED) == 3
    captured = capsys.readouterr()
    assert "duplicated" in captured.err and "CI_REGISTRY_IMAGE" in captured.err
    assert "CI_DEFAULT_BRANCH" not in captured.err
    assert "registry.example" not in captured.out + captured.err


def test_duplicate_across_required_and_protected_lists_fails(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {})
    monkeypatch.setattr(check_ci_config, "REQUIRED", ("CI_REGISTRY_IMAGE",))
    monkeypatch.setattr(check_ci_config, "PROTECTED_REQUIRED", ("CI_REGISTRY_IMAGE",))
    assert _run(project, REQUIRED) == 3
    assert "CI_REGISTRY_IMAGE" in capsys.readouterr().err


def test_empty_name_fails(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {})
    _declare(monkeypatch, ("CI_REGISTRY_IMAGE", ""))
    assert _run(project, {**REQUIRED, "": "secret-value"}) == 3
    captured = capsys.readouterr()
    assert "empty" in captured.err and "''" in captured.err
    assert "secret-value" not in captured.out + captured.err


def test_whitespace_only_name_fails(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {})
    _declare(monkeypatch, ("CI_REGISTRY_IMAGE", "  ", "\t"))
    assert _run(project, {**REQUIRED, "  ": "secret-value"}) == 3
    captured = capsys.readouterr()
    assert "empty" in captured.err and "'  '" in captured.err and "'\\t'" in captured.err
    assert "secret-value" not in captured.out + captured.err
