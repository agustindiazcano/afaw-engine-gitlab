"""Tests for scripts.human_only_files: a WEAK backup control for the human-only files."""

from __future__ import annotations

import urllib.error
from typing import TYPE_CHECKING, Any

import pytest

from scripts import human_only_files as hof

if TYPE_CHECKING:
    from tests.tooling.conftest import Project

OLD_CONFIG = {"mutation_min_score": 80, "code_prefixes": ["src/"], "dashboard": {"stale_days": 3}}


def test_unprotected_files_are_not_reported() -> None:
    assert hof.protected_changes(["src/a.py", "README.md"], OLD_CONFIG, OLD_CONFIG) == []


@pytest.mark.parametrize(
    "path",
    [".gitlab-ci.yml", "AGENTS.md", "state/equivalent_mutants.json", "deploy/run.yaml"],
)
def test_human_only_paths_are_reported(path: str) -> None:
    assert hof.protected_changes([path], OLD_CONFIG, OLD_CONFIG) == [path]


def test_config_change_is_reported_only_for_mutation_and_gate_keys() -> None:
    dashboard = {**OLD_CONFIG, "dashboard": {"stale_days": 9}}
    assert hof.protected_changes(["state/config.json"], OLD_CONFIG, dashboard) == []
    weaker = {**OLD_CONFIG, "mutation_min_score": 10}
    assert hof.protected_changes(["state/config.json"], OLD_CONFIG, weaker) == [
        "state/config.json (mutation_min_score)"
    ]


def test_a_user_the_humans_filter_excludes_is_not_human() -> None:
    assert hof.is_human([], set()) is False


def test_a_listed_id_is_not_human_even_when_gitlab_returns_it() -> None:
    assert hof.is_human([{"id": 7}], {7}) is False


def test_an_unlisted_user_returned_by_the_humans_filter_is_human() -> None:
    assert hof.is_human([{"id": 8}], {7}) is True


def test_commit_identities_only_warn() -> None:
    identities = ["Dev <dev@example.com>", "x <project_1_bot@noreply.gitlab.com>"]
    warnings = hof.commit_warnings(identities)
    assert len(warnings) == 1 and "bot" in warnings[0]


def _run(
    project: Project,
    monkeypatch: pytest.MonkeyPatch,
    changed: list[str],
    users: dict[str, dict[str, Any]],
    env: dict[str, str] | None = None,
    identities: list[str] | None = None,
) -> int:
    monkeypatch.setattr(hof, "changed_files", lambda base, root: changed)
    monkeypatch.setattr(hof, "config_at", lambda base, root: OLD_CONFIG)
    monkeypatch.setattr(hof, "commit_identities", lambda base, root: identities or [])
    project.write("state/config.json", OLD_CONFIG)

    def fake_fetch(url: str, token: str | None) -> Any:
        for key, value in users.items():
            if url.endswith(key):
                return value
        raise urllib.error.URLError(f"no answer for {url}")

    monkeypatch.setattr(hof, "fetch_json", fake_fetch)
    for key, value in {
        "CI_API_V4_URL": "https://gl/api/v4",
        "CI_PROJECT_ID": "1",
        "CI_MERGE_REQUEST_IID": "5",
        "GITLAB_USER_LOGIN": "pusher",
        **(env or {}),
    }.items():
        monkeypatch.setenv(key, value)
    return hof.main(["--root", str(project.root), "--base", "origin/main"])


MR = "/projects/1/merge_requests/5"
PUSHER = "/users?username=pusher&humans=true"
AUTHOR = "/users?username=author&humans=true"
HUMAN = {MR: {"author": {"username": "author"}}, PUSHER: [{"id": 8}], AUTHOR: [{"id": 9}]}


def test_no_protected_change_passes_without_calling_the_api(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(project, monkeypatch, ["src/a.py"], {}) == 0
    assert "No human-only file" in capsys.readouterr().out


def test_human_author_may_change_a_protected_file(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(project, monkeypatch, ["AGENTS.md"], HUMAN) == 0


def test_bot_author_changing_a_protected_file_fails_and_says_the_control_is_weak(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    users = {**HUMAN, AUTHOR: []}
    assert _run(project, monkeypatch, [".gitlab-ci.yml"], users) == 1
    captured = capsys.readouterr()
    assert "WEAK" in captured.out and "PROBLEM" in captured.err


def test_a_non_human_pusher_fails_even_with_a_human_author(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    users = {**HUMAN, PUSHER: []}
    assert _run(project, monkeypatch, ["AGENTS.md"], users) == 1


def test_unreadable_author_fails_closed(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(project, monkeypatch, ["AGENTS.md"], {}) == 2


def test_ids_from_the_group_variable_are_non_human(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(project, monkeypatch, ["AGENTS.md"], HUMAN, {"AFAW_BOT_USER_IDS": "9, 11"}) == 1


def test_output_is_text_not_json(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(project, monkeypatch, ["AGENTS.md"], HUMAN)
    assert not capsys.readouterr().out.lstrip().startswith("{")


def test_an_unidentifiable_author_never_blocks_a_change_without_protected_files(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fail-closed applies only when a human-only file changed; other merge requests pass."""
    monkeypatch.setattr(hof, "changed_files", lambda base, root: ["src/a.py", "README.md"])
    monkeypatch.setattr(hof, "config_at", lambda base, root: OLD_CONFIG)
    monkeypatch.setattr(hof, "fetch_json", lambda url, token: pytest.fail("API was called"))
    for var in ("CI_API_V4_URL", "CI_PROJECT_ID", "CI_MERGE_REQUEST_IID", "GITLAB_USER_LOGIN"):
        monkeypatch.delenv(var, raising=False)
    project.write("state/config.json", OLD_CONFIG)
    assert hof.main(["--root", str(project.root), "--base", "origin/main"]) == 0
    assert "nothing to check" in capsys.readouterr().out


def test_a_flow_service_account_may_change_unprotected_files(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    users = {**HUMAN, AUTHOR: [], PUSHER: []}  # both are non-human (the flows' service account)
    assert _run(project, monkeypatch, ["src/a.py", "tests/test_a.py"], users) == 0


SA_COMMIT = "Duo Developer <service_account_group_1_ab12@noreply.gitlab.com>"


def test_service_account_commits_are_picked_out_by_the_address() -> None:
    identities = ["Dev <dev@example.com>", SA_COMMIT, "Fake <x@noreply.gitlab.com>"]
    assert hof.service_account_commits(identities) == [SA_COMMIT]


def test_a_commit_authored_by_a_service_account_fails_even_with_a_human_pusher_and_author(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(project, monkeypatch, ["AGENTS.md"], HUMAN, identities=[SA_COMMIT]) == 1
    assert "service account" in capsys.readouterr().err


@pytest.mark.characterization(
    reason="a flow's commits on unprotected files were always allowed; this pins that they stay so"
)
def test_a_service_account_commit_on_unprotected_files_is_fine(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(project, monkeypatch, ["src/a.py"], {}, identities=[SA_COMMIT]) == 0


def test_protected_patterns_are_the_script_constants_sorted() -> None:
    expected = sorted((*hof.HUMAN_ONLY_PATHS, *hof.HUMAN_ONLY_PREFIXES))
    assert hof.protected_patterns() == expected


def test_list_prints_the_patterns_one_per_line_without_base(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert hof.main(["--list"]) == 0
    assert capsys.readouterr().out.splitlines() == hof.protected_patterns()


def test_without_list_and_without_base_still_fails(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        hof.main([])
    assert raised.value.code == 2
    assert "--base" in capsys.readouterr().err
