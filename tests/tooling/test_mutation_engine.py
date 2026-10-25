"""mutation_engine: run mutmut on the required files of a branch and write the gate's results."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from scripts import mutation_engine

if TYPE_CHECKING:
    from tests.tooling.conftest import Project

REQUIRED = "src/afaw_web/app.py"
META = {"exit_code_by_key": {"afaw_web.app.x_f__mutmut_1": 1, "afaw_web.app.x_f__mutmut_2": 0}}


class FakeMutmut:
    """Stands for ``python -m mutmut run``: it records the call and writes the .meta files."""

    def __init__(self, root: Path, meta: dict[str, Any] | None = META, raises: bool = False):
        self.root, self.meta, self.raises, self.calls = root, meta, raises, []

    def __call__(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, kwargs, (self.root / "setup.cfg").read_text("utf-8")))
        if self.raises:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if self.meta is not None:
            target = self.root / "mutants" / "src" / "afaw_web" / "app.py.meta"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(self.meta), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")


def run(
    project: Project,
    monkeypatch: pytest.MonkeyPatch,
    changed: list[str],
    fake: FakeMutmut | None = None,
    extra: list[str] | None = None,
) -> tuple[int, Path]:
    monkeypatch.setattr(mutation_engine, "changed_files", lambda base, root: changed)
    project.write("state/config.json", {"mutation_critical_paths": ["src/afaw_web/"]})
    if fake is not None:
        monkeypatch.setattr(mutation_engine.subprocess, "run", fake)
    out = project.root / "build" / "mutation.json"
    args = ["--root", str(project.root), "--base", "origin/main", "--out", str(out)]
    return mutation_engine.main([*args, *(extra or [])]), out


def test_the_config_names_the_directory_the_files_and_the_tests() -> None:
    text = mutation_engine.mutmut_config([REQUIRED], "tests/web")
    assert text == (
        "[mutmut]\n"
        "source_paths=src/afaw_web/\n"
        "only_mutate=src/afaw_web/app.py\n"
        "pytest_add_cli_args_test_selection=tests/web\n"
    )


def test_several_files_are_one_pattern_per_line_because_mutmut_does_not_split_on_commas() -> None:
    text = mutation_engine.mutmut_config(["src/afaw_web/app.py", "src/afaw_web/search.py"], "t")
    assert "only_mutate=src/afaw_web/app.py\n  src/afaw_web/search.py\n" in text


def test_files_in_two_directories_are_not_supported() -> None:
    with pytest.raises(mutation_engine.EngineError, match="not verified"):
        mutation_engine.mutmut_config(["src/a/x.py", "src/b/y.py"], "tests/web")


def test_with_no_required_file_it_says_so_and_runs_nothing(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeMutmut(project.root)
    code, out = run(project, monkeypatch, ["docs/a.md", "src/other/x.py"], fake)
    assert code == 0 and fake.calls == [] and not out.exists()
    assert "NO MANDATORY FILES" in capsys.readouterr().out


def test_it_runs_mutmut_with_a_timeout_and_writes_the_results(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeMutmut(project.root)
    code, out = run(project, monkeypatch, [REQUIRED, "README.md"], fake, ["--timeout", "99"])
    assert code == 0
    command, kwargs, config = fake.calls[0]
    assert command[-2:] == ["mutmut", "run"] and kwargs["timeout"] == 99
    assert kwargs["cwd"] == project.root
    assert "only_mutate=src/afaw_web/app.py" in config
    written = json.loads(out.read_text(encoding="utf-8"))
    assert [m["status"] for m in written["files"][REQUIRED]["mutants"]] == ["killed", "survived"]


def test_an_existing_setup_cfg_is_never_overwritten(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (project.root / "setup.cfg").write_text("[flake8]\n", encoding="utf-8")
    fake = FakeMutmut(project.root)
    code, _ = run(project, monkeypatch, [REQUIRED], fake)
    assert code == 2 and fake.calls == []
    assert "setup.cfg" in capsys.readouterr().err
    assert (project.root / "setup.cfg").read_text("utf-8") == "[flake8]\n"


def test_a_timeout_fails_loudly(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(project, monkeypatch, [REQUIRED], FakeMutmut(project.root, raises=True))
    assert code == 2 and not out.exists()
    assert "timed out" in capsys.readouterr().err


def test_a_run_that_leaves_no_results_fails_loudly(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(project, monkeypatch, [REQUIRED], FakeMutmut(project.root, meta=None))
    assert code == 2 and not out.exists()
    assert "ERROR" in capsys.readouterr().err
