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
