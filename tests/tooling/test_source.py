import json
import subprocess
from datetime import UTC, datetime

import pytest

from scripts.afaw_state import source
from scripts.afaw_state.source import _load, git_runner, list_files, read_source
from tests.tooling.helpers import make_task

ADR = "docs/adr/0001-first.md"
GOTCHA = "docs/gotchas/0001-trap.md"
ADR_TEXT = "---\nstatus: accepted\ndate: 2026-10-01\n---\n# First\n## Context\n"
GOTCHA_TEXT = "---\nstatus: active\ndate: 2026-10-02\n---\n# Trap\n## Symptom\n"


def fake_git(tree, files, commit_time="2026-10-25T12:30:00+00:00\n"):
    """A git runner over an in-memory tree: ``tree`` lists paths, ``files`` maps path to text."""
    calls: list[list[str]] = []

    def run(args):
        calls.append(args)
        if args[0] == "ls-tree":
            folder = args[-1]
            return "\n".join(p for p in tree if p.startswith(folder)) + "\n"
        if args[0] == "show":
            return files[args[1].split(":", 1)[1]]
        if args[0] == "log":
            return commit_time
        raise AssertionError(args)

    run.calls = calls  # type: ignore[attr-defined]
    return run


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_git_runner_runs_git_and_returns_its_stdout(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"], seen["kwargs"] = cmd, kwargs
        return subprocess.CompletedProcess(cmd, 0, stdout="out\n", stderr="")

    monkeypatch.setattr(source.subprocess, "run", fake_run)
    assert git_runner(["show", "main:x"]) == "out\n"
    assert seen["cmd"] == ["git", "show", "main:x"]
    assert seen["kwargs"] == {"check": True, "capture_output": True, "text": True}


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_git_runner_raises_when_git_fails(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(128, cmd)

    monkeypatch.setattr(source.subprocess, "run", fake_run)
    with pytest.raises(subprocess.CalledProcessError):
        git_runner(["show", "main:missing"])


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_load_parses_json_at_the_ref():
    run = fake_git([], {"a.json": '{"k": 1}'})
    assert _load(run, "origin/main", "a.json") == {"k": 1}
    assert run.calls == [["show", "origin/main:a.json"]]


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_load_names_the_path_and_ref_of_invalid_json():
    run = fake_git([], {"a.json": "{not json"})
    with pytest.raises(ValueError, match=r"^a\.json at origin/main is not valid JSON: "):
        _load(run, "origin/main", "a.json")


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_list_files_filters_by_suffix_and_sorts():
    run = fake_git(["f/b.json", "f/a.json", "f/readme.md"], {})
    assert list_files(run, "ref", "f") == ["f/a.json", "f/b.json"]
    assert list_files(run, "ref", "f", ".md") == ["f/readme.md"]
    assert run.calls[0] == ["ls-tree", "-r", "--name-only", "ref", "--", "f"]


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_list_files_of_an_empty_folder_is_empty():
    assert list_files(fake_git([], {}), "ref", "f") == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_read_source_collects_tasks_deltas_knowledge_config_and_time():
    t1, t2 = make_task("task_001"), make_task("task_002")
    delta = {"summary": "s"}
    run = fake_git(
        [
            "state/tasks/task_002.json",
            "state/tasks/task_001.json",
            "state/tasks/notes.txt",
            "context/tasks/task_001_context.json",
            "context/tasks/other.json",
            "state/config.json",
            ADR,
            "docs/adr/sub/0002-nested.md",
            GOTCHA,
        ],
        {
            "state/tasks/task_001.json": json.dumps(t1),
            "state/tasks/task_002.json": json.dumps(t2),
            "context/tasks/task_001_context.json": json.dumps(delta),
            "state/config.json": json.dumps({"dashboard": {"stale_days": 3}, "other": 1}),
            ADR: ADR_TEXT,
            GOTCHA: GOTCHA_TEXT,
        },
    )
    result = read_source("origin/main", run)
    assert set(result) == {"tasks", "deltas", "knowledge", "config", "as_of"}
    assert result["tasks"] == [t1, t2]
    assert result["deltas"] == {"task_001": delta}
    assert result["config"] == {"stale_days": 3}
    assert result["as_of"] == datetime(2026, 10, 25, 12, 30, tzinfo=UTC)
    knowledge = result["knowledge"]
    assert [(d["kind"], d["id"], d["path"]) for d in knowledge] == [
        ("adr", "0001", ADR),
        ("gotcha", "0001", GOTCHA),
    ]
    assert knowledge[0]["meta"] == {"status": "accepted", "date": "2026-10-01"}
    assert ["log", "-1", "--format=%cI", "origin/main"] in run.calls


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_read_source_without_config_or_files_uses_defaults():
    run = fake_git([], {})
    result = read_source("origin/main", run)
    assert result["tasks"] == []
    assert result["deltas"] == {}
    assert result["knowledge"] == []
    assert result["config"] == {}


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_read_source_config_without_dashboard_section_is_empty():
    run = fake_git(["state/config.json"], {"state/config.json": json.dumps({"x": 1})})
    assert read_source("ref", run)["config"] == {}


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_read_source_reads_every_file_from_the_given_ref():
    run = fake_git(
        ["state/tasks/task_001.json", "state/config.json", ADR],
        {
            "state/tasks/task_001.json": json.dumps(make_task()),
            "state/config.json": "{}",
            ADR: ADR_TEXT,
        },
    )
    read_source("abc123", run)
    shown = [c[1] for c in run.calls if c[0] == "show"]
    assert shown and all(arg.startswith("abc123:") for arg in shown)


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_read_source_rejects_an_invalid_task_file():
    run = fake_git(["state/tasks/task_001.json"], {"state/tasks/task_001.json": "oops"})
    with pytest.raises(ValueError, match="state/tasks/task_001.json at ref is not valid JSON"):
        read_source("ref", run)
