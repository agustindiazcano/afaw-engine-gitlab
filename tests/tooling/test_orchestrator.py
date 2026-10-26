"""The orchestrator picks the next task from the derived pending view, in code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.orchestrator import main, select_next


def _t(tid: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": tid, "status": "pending", "owner": "agent", "priority": 3,
        "difficulty_estimate": 2, "blocked_by": [], "title": f"title {tid}",
    }
    base.update(kw)
    return base


def test_lowest_priority_number_wins() -> None:
    chosen = select_next([_t("task_2", priority=2), _t("task_1", priority=4)])
    assert chosen is not None and chosen["id"] == "task_2"


def test_ties_break_on_difficulty_then_id() -> None:
    tasks = [_t("task_9", difficulty_estimate=1), _t("task_3", difficulty_estimate=2),
             _t("task_1", difficulty_estimate=2)]
    chosen = select_next(tasks)
    assert chosen is not None and chosen["id"] == "task_9"
    tasks = tasks[1:]
    chosen = select_next(tasks)
    assert chosen is not None and chosen["id"] == "task_1"


def test_skips_in_progress_human_and_blocked_tasks() -> None:
    tasks = [
        _t("task_1", status="in_progress", priority=1),
        _t("task_2", owner="human", priority=1),
        _t("task_3", blocked_by=["task_4"], priority=1),
        _t("task_4", status="backlog", priority=5),
    ]
    chosen = select_next(tasks)
    assert chosen is not None and chosen["id"] == "task_4"


def test_a_blocker_that_is_not_open_does_not_block() -> None:
    chosen = select_next([_t("task_1", blocked_by=["task_0"])])
    assert chosen is not None and chosen["id"] == "task_1"


def test_nothing_eligible_gives_none() -> None:
    assert select_next([_t("task_1", status="in_progress")]) is None
    assert select_next([]) is None


def test_main_prints_the_selection_and_the_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    view = tmp_path / "pending.json"
    view.write_text(json.dumps([_t("task_7", priority=1)]), encoding="utf-8")
    assert main(["--pending", str(view)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["selected"]["id"] == "task_7"
    assert "priority 1" in out["reason"]


def test_main_with_no_candidate_prints_null(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    view = tmp_path / "pending.json"
    view.write_text("[]", encoding="utf-8")
    assert main(["--pending", str(view)]) == 0
    assert json.loads(capsys.readouterr().out)["selected"] is None


def test_main_fails_loudly_on_a_missing_view(tmp_path: Path) -> None:
    assert main(["--pending", str(tmp_path / "missing.json")]) == 2


# ------------------------------------------------------------------ filing the issue (--create)


class FakeIssueApi:
    def __init__(self, open_issues: list[dict[str, Any]] | None = None) -> None:
        self.open_issues = open_issues or []
        self.created: list[dict[str, Any]] = []

    def labeled_issues(self, label: str) -> list[dict[str, Any]]:
        return self.open_issues

    def user_id(self, username: str) -> int:
        return 33073386

    def create_issue(self, title: str, description: str, assignee_id: int, label: str) -> None:
        self.created.append(
            {"title": title, "description": description, "assignee": assignee_id, "label": label}
        )


def test_the_issue_names_the_task_and_carries_the_rules() -> None:
    from scripts.orchestrator import issue_text, issue_title, marker

    task = _t("task_77", title="Add a stats endpoint", priority=2, role="architect")
    assert issue_title(task) == "feat(task_77): Add a stats endpoint"
    text = issue_text(task)
    assert "task_77" in text and "Add a stats endpoint" in text
    assert "strict TDD" in text and "red_check" in text
    assert ".gitlab-ci.yml" in text  # the files it must not touch
    assert marker("task_77") in text


def test_create_files_one_issue_for_the_flow() -> None:
    from scripts.orchestrator import LABEL, create_issue

    api = FakeIssueApi()
    assert create_issue(api, _t("task_77")) == "created"
    assert len(api.created) == 1
    assert api.created[0]["assignee"] == 33073386 and api.created[0]["label"] == LABEL


def test_create_does_not_file_the_same_task_twice() -> None:
    from scripts.orchestrator import create_issue, marker

    api = FakeIssueApi([{"description": f"text {marker('task_77')}"}])
    assert create_issue(api, _t("task_77")) == "exists"
    assert api.created == []


def test_main_create_without_a_token_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    view = tmp_path / "pending.json"
    view.write_text(json.dumps([_t("task_7")]), encoding="utf-8")
    monkeypatch.delenv("AFAW_MERGE_TOKEN", raising=False)
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    assert main(["--pending", str(view), "--create", "--project", "1"]) == 2
    assert "token" in capsys.readouterr().err


@pytest.mark.characterization(reason="documents that the selection alone never writes")
def test_main_without_create_never_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    view = tmp_path / "pending.json"
    view.write_text(json.dumps([_t("task_7")]), encoding="utf-8")
    monkeypatch.setenv("GITLAB_TOKEN", "x")
    assert main(["--pending", str(view)]) == 0
