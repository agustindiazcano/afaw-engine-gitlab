"""Tests for scripts.build_state, run in-process so that its entry point is measured."""

from __future__ import annotations

import json
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import build_state
from tests.tooling.helpers import make_task

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

COMMIT_TIME = "2026-09-30T12:00:00+00:00"


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_COMMITTER_DATE": COMMIT_TIME,
            "GIT_AUTHOR_DATE": COMMIT_TIME,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "state/tasks").mkdir(parents=True)
    (tmp_path / "context/tasks").mkdir(parents=True)
    (tmp_path / "state/tasks/task_001.json").write_text(
        json.dumps(make_task(status="done", branch="feat/a"))
    )
    (tmp_path / "state/tasks/task_002.json").write_text(json.dumps(make_task("task_002")))
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "init")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def metrics_of(out: Path) -> dict[str, object]:
    return json.loads((out / "metrics.json").read_text(encoding="utf-8"))


def test_prepare_out_creates_a_marked_directory(tmp_path: Path) -> None:
    out = tmp_path / "a" / "b"
    build_state.prepare_out(out)
    assert sorted(p.name for p in out.iterdir()) == [build_state.MARKER]


def test_prepare_out_empties_a_marked_directory_and_keeps_the_marker(tmp_path: Path) -> None:
    out = tmp_path / "build"
    out.mkdir()
    (out / build_state.MARKER).touch()
    (out / "old.json").write_text("{}")
    (out / "sub").mkdir()
    (out / "sub" / "deep.txt").write_text("x")
    build_state.prepare_out(out)
    assert [p.name for p in out.iterdir()] == [build_state.MARKER]


def test_prepare_out_refuses_an_unmarked_directory(tmp_path: Path) -> None:
    out = tmp_path / "mine"
    out.mkdir()
    (out / "keep.txt").write_text("mine")
    with pytest.raises(SystemExit) as exc:
        build_state.prepare_out(out)
    assert str(exc.value) == f"refusing to overwrite {out}: it is not an AFAW build directory"
    assert (out / "keep.txt").read_text() == "mine"


def test_main_writes_the_views_and_reports_them(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = repo / "build" / "state"
    assert build_state.main(["--ref", "main", "--out", str(out)]) == 0
    written = sorted(p for p in out.rglob("*") if p.is_file() and p.name != build_state.MARKER)
    stdout = capsys.readouterr().out
    assert stdout == f"wrote {len(written)} views to {out} (as of {COMMIT_TIME})\n"
    assert (out / build_state.MARKER).exists()
    assert metrics_of(out)["as_of"] == COMMIT_TIME
    pending = json.loads((out / "pending.json").read_text(encoding="utf-8"))
    assert [row["id"] for row in pending] == ["task_002"]


def test_main_default_ref_is_origin_main(repo: Path) -> None:
    # The temporary repository has no origin/main, so the default ref cannot be read.
    with pytest.raises(subprocess.CalledProcessError):
        build_state.main(["--out", str(repo / "build" / "state")])


def test_main_accepts_an_explicit_as_of(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = repo / "out"
    assert (
        build_state.main(["--ref", "main", "--out", str(out), "--as-of", "2026-10-02T08:00:00Z"])
        == 0
    )
    assert metrics_of(out)["as_of"] == "2026-10-02T08:00:00+00:00"
    assert capsys.readouterr().out.endswith("(as of 2026-10-02T08:00:00+00:00)\n")


def test_main_rejects_as_of_without_time_zone(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = repo / "out"
    assert (
        build_state.main(["--ref", "main", "--out", str(out), "--as-of", "2026-10-02T08:00:00"])
        == 2
    )
    captured = capsys.readouterr()
    assert captured.err == "--as-of needs a time zone: '2026-10-02T08:00:00'\n"
    assert captured.out == ""
    assert not out.exists()


def test_main_rejects_an_unparsable_as_of(repo: Path) -> None:
    with pytest.raises(ValueError):
        build_state.main(["--ref", "main", "--out", str(repo / "out"), "--as-of", "yesterday"])


def test_main_reads_facts_from_a_file(repo: Path) -> None:
    facts = repo / "facts.json"
    facts.write_text(
        json.dumps(
            {
                "task_001": {
                    "started_at": "2026-09-20T10:00:00Z",
                    "first_green_at": "2026-09-20T11:00:00Z",
                    "pr_opened_at": "2026-09-20T11:00:00Z",
                    "merged_at": "2026-09-21T10:00:00Z",
                    "ci": {
                        "runs": 2,
                        "failed_runs": 0,
                        "jobs": 4,
                        "queue_seconds": 30,
                        "job_minutes": 7,
                    },
                }
            }
        )
    )
    with_facts = repo / "with"
    without = repo / "without"
    assert build_state.main(["--ref", "main", "--out", str(with_facts), "--facts", str(facts)]) == 0
    assert build_state.main(["--ref", "main", "--out", str(without)]) == 0
    assert metrics_of(with_facts) != metrics_of(without)
    assert (with_facts / "dashboard.html").read_bytes() != (without / "dashboard.html").read_bytes()


def test_main_fails_loudly_on_invalid_state_and_writes_nothing(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "state/tasks/task_003.json").write_text(
        json.dumps(make_task("task_003", light="green"))
    )
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "bad")
    out = repo / "out"
    assert build_state.main(["--ref", "main", "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("invalid source state:\n")
    assert "task_003: derived field must not be declared: light" in captured.err
    assert captured.out == ""
    assert not out.exists()


def test_main_refuses_a_foreign_output_directory(repo: Path) -> None:
    out = repo / "mine"
    out.mkdir()
    (out / "keep.txt").write_text("mine")
    with pytest.raises(SystemExit) as exc:
        build_state.main(["--ref", "main", "--out", str(out)])
    assert "refusing to overwrite" in str(exc.value)
    assert (out / "keep.txt").exists()


def test_running_the_module_exits_with_the_status_of_main(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = repo / "out"
    monkeypatch.setattr("sys.argv", ["build_state", "--ref", "main", "--out", str(out)])
    monkeypatch.delitem(sys.modules, "scripts.build_state")
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("scripts.build_state", run_name="__main__")
    assert exc.value.code == 0
    assert (out / "pending.json").exists()
