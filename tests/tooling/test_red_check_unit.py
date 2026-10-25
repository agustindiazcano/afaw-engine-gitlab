"""Unit tests for scripts.red_check with git and pytest subprocesses mocked (no real repository)."""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import red_check
from scripts.state_common import StateError

# ------------------------------------------------------------------------------------- _git


class _Completed:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


def test_git_returns_stdout_and_passes_a_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> _Completed:
        calls.append((cmd, kwargs))
        return _Completed("out\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert red_check._git(tmp_path, "rev-parse", "HEAD") == "out\n"
    cmd, kwargs = calls[0]
    assert cmd == ["git", "rev-parse", "HEAD"]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["timeout"] == red_check.GIT_TIMEOUT_SECONDS == 60
    assert kwargs["check"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(128, ["git"]),
        subprocess.TimeoutExpired(["git"], 60),
        FileNotFoundError("git"),
    ],
    ids=["nonzero-exit", "timeout", "git-missing"],
)
def test_git_failure_becomes_a_state_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, error: Exception
) -> None:
    def fake_run(*_args: Any, **_kwargs: Any) -> _Completed:
        raise error

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(StateError, match=r"^git show HEAD:x failed: ") as info:
        red_check._git(tmp_path, "show", "HEAD:x")
    assert info.value.__cause__ is error


# --------------------------------------------------------------------------------- test_ids


def test_test_ids_includes_async_tests_and_skips_other_classes() -> None:
    source = """
async def test_async():
    pass


def _test_private():
    pass


class TestKinds:
    async def test_async_method(self):
        pass

    def helper(self):
        pass


class Helper:
    def test_not_collected(self):
        pass
"""
    assert red_check.test_ids(source) == {"test_async", "TestKinds::test_async_method"}


def test_added_tests_of_an_unchanged_file_is_empty() -> None:
    source = "def test_a():\n    pass\n"
    assert red_check.added_tests("tests/a.py", source, source) == []


# ----------------------------------------------------------------------------- _junit_key


def test_junit_key_of_a_top_level_test() -> None:
    assert red_check._junit_key("tests/tooling/test_x.py::test_a") == (
        "tests.tooling.test_x",
        "test_a",
    )


def test_junit_key_of_a_method_includes_the_class() -> None:
    assert red_check._junit_key("tests/test_x.py::TestG::test_a") == (
        "tests.test_x.TestG",
        "test_a",
    )


# ------------------------------------------------------------------------------- not_red


def _report(*cases: str) -> str:
    return "<testsuites><testsuite>" + "".join(cases) + "</testsuite></testsuites>"


def test_a_test_with_an_error_element_is_red() -> None:
    report = _report(
        '<testcase classname="tests.test_x" name="test_a"><error message="e"/></testcase>'
    )
    assert red_check.not_red(report, ["tests/test_x.py::test_a"]) == ([], [])


def test_a_passing_test_is_reported_as_passing() -> None:
    report = _report('<testcase classname="tests.test_x" name="test_a"/>')
    assert red_check.not_red(report, ["tests/test_x.py::test_a"]) == (
        ["tests/test_x.py::test_a"],
        [],
    )


def test_a_collection_entry_without_failure_does_not_break_the_module() -> None:
    report = _report(
        '<testcase classname="" name="tests.test_x"/>',
        '<testcase classname="tests.test_x" name="test_a"/>',
    )
    assert red_check.not_red(report, ["tests/test_x.py::test_a"]) == (
        ["tests/test_x.py::test_a"],
        [],
    )


def test_a_broken_module_does_not_hide_tests_of_another_module() -> None:
    report = _report(
        '<testcase classname="" name="tests.test_y"><error message="ImportError"/></testcase>',
        '<testcase classname="tests.test_x" name="test_a"/>',
    )
    passing, missing = red_check.not_red(
        report, ["tests/test_x.py::test_a", "tests/test_y.py::test_b", "tests/test_z.py::test_c"]
    )
    assert passing == ["tests/test_x.py::test_a"]
    assert missing == ["tests/test_z.py::test_c"]


def test_a_failed_test_does_not_make_a_sibling_test_red() -> None:
    report = _report(
        '<testcase classname="tests.test_x" name="test_a"><failure message="f"/></testcase>',
        '<testcase classname="tests.test_x" name="test_b"/>',
    )
    assert red_check.not_red(report, ["tests/test_x.py::test_a", "tests/test_x.py::test_b"]) == (
        ["tests/test_x.py::test_b"],
        [],
    )


# ------------------------------------------------------------------ _is_characterization


def _decorator(code: str) -> ast.expr:
    function = ast.parse(f"@{code}\ndef f(): pass").body[0]
    assert isinstance(function, ast.FunctionDef)
    return function.decorator_list[0]


def test_reason_is_read_from_the_keyword() -> None:
    decorator = _decorator('pytest.mark.characterization(reason="why")')
    assert red_check._is_characterization(decorator) == "why"


def test_reason_is_read_from_the_positional_argument() -> None:
    decorator = _decorator('pytest.mark.characterization("positional")')
    assert red_check._is_characterization(decorator) == "positional"


def test_a_call_without_a_string_reason_gives_an_empty_reason() -> None:
    assert (
        red_check._is_characterization(_decorator("pytest.mark.characterization(reason=1)")) == ""
    )
    assert red_check._is_characterization(_decorator("pytest.mark.characterization()")) == ""


def test_a_bare_marker_gives_an_empty_reason() -> None:
    assert red_check._is_characterization(_decorator("pytest.mark.characterization")) == ""


def test_other_decorators_are_not_characterization() -> None:
    assert red_check._is_characterization(_decorator("pytest.mark.slow")) is None
    assert red_check._is_characterization(_decorator('pytest.mark.skip(reason="x")')) is None
    assert red_check._is_characterization(_decorator("staticmethod")) is None
    assert red_check._is_characterization(_decorator("characterization")) is None


# ------------------------------------------------------------------- characterization


def test_characterization_finds_methods_and_async_tests() -> None:
    source = """
import pytest


class TestGroup:
    @pytest.mark.characterization(reason="method")
    def test_method(self):
        pass

    @pytest.mark.slow
    def test_other(self):
        pass


class Helper:
    @pytest.mark.characterization(reason="ignored class")
    def test_hidden(self):
        pass


@pytest.mark.characterization(reason="async one")
async def test_async():
    pass


@pytest.mark.characterization(reason="not a test")
def helper():
    pass
"""
    assert red_check.characterization("tests/t.py", source) == {
        "tests/t.py::TestGroup::test_method": "method",
        "tests/t.py::test_async": "async one",
    }


# -------------------------------------------------------------------------- _is_test_file


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/test_a.py", True),
        ("tests/sub/a_test.py", True),
        ("tests/conftest.py", False),
        ("tests/test_a.txt", False),
        ("src/test_a.py", False),
        ("tests/helpers.py", False),
    ],
)
def test_is_test_file(path: str, expected: bool) -> None:
    assert red_check._is_test_file(path, ("tests/",)) is expected


def test_is_test_file_honours_every_prefix() -> None:
    assert red_check._is_test_file("spec/test_a.py", ("tests/", "spec/")) is True


# --------------------------------------------------------------------- skip_declaration


def _fake_git(files: dict[str, str], changed: list[str]) -> Any:
    def fake(_root: Path, *args: str) -> str:
        if args[0] == "diff":
            return "\n".join(changed)
        assert args[0] == "show"
        return files[args[1]]

    return fake


def test_skip_declaration_reports_the_first_skipping_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    files = {
        "HEAD:state/tasks/task_001.json": json.dumps({"id": "task_001", "type": "feature"}),
        "HEAD:state/tasks/task_002.json": json.dumps({"id": "task_002", "type": "refactor"}),
        "HEAD:state/tasks/task_003.json": json.dumps({"id": "task_003", "type": "tests-only"}),
    }
    changed = [
        "state/tasks/task_003.json",
        "state/tasks/task_002.json",
        "state/tasks/task_001.json",
    ]
    monkeypatch.setattr(red_check, "_git", _fake_git(files, changed))
    # Paths are sorted, so task_002 is found before task_003.
    assert (
        red_check.skip_declaration(tmp_path, "base") == "SKIPPED: task_002 declares type refactor"
    )


def test_skip_declaration_falls_back_to_the_path_when_the_id_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    files = {"HEAD:state/tasks/x.json": json.dumps({"type": "tests-only"})}
    monkeypatch.setattr(red_check, "_git", _fake_git(files, ["state/tasks/x.json"]))
    assert (
        red_check.skip_declaration(tmp_path, "base")
        == "SKIPPED: state/tasks/x.json declares type tests-only"
    )


def test_skip_declaration_ignores_invalid_json_and_non_objects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    files = {
        "HEAD:state/tasks/a.json": "{not json",
        "HEAD:state/tasks/b.json": json.dumps(["tests-only"]),
        "HEAD:state/tasks/c.json": json.dumps({"id": "c", "type": "chore"}),
    }
    changed = ["state/tasks/a.json", "state/tasks/b.json", "state/tasks/c.json"]
    monkeypatch.setattr(red_check, "_git", _fake_git(files, changed))
    assert red_check.skip_declaration(tmp_path, "base") is None


def test_skip_declaration_asks_git_only_for_added_or_modified_task_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[tuple[str, ...]] = []

    def fake(_root: Path, *args: str) -> str:
        seen.append(args)
        return ""

    monkeypatch.setattr(red_check, "_git", fake)
    assert red_check.skip_declaration(tmp_path, "abc") is None
    assert seen == [("diff", "--name-only", "--diff-filter=AM", "abc", "HEAD", "--", "state/tasks")]


# ------------------------------------------------------------------------------ run_old


class _Runner:
    """Records git and pytest calls of run_old; pytest writes ``report`` if it is not None."""

    def __init__(self, report: str | None, sources: dict[str, str] | None = None) -> None:
        self.report = report
        self.sources = sources or {}
        self.git_calls: list[tuple[str, ...]] = []
        self.pytest_calls: list[tuple[list[str], dict[str, Any]]] = []
        self.tree: Path | None = None

    def git(self, _root: Path, *args: str) -> str:
        self.git_calls.append(args)
        if args[0] == "worktree" and args[1] == "add":
            self.tree = Path(args[3])
        if args[0] == "show":
            return self.sources[args[1]]
        return ""

    def run(self, cmd: list[str], **kwargs: Any) -> None:
        self.pytest_calls.append((cmd, kwargs))
        if self.report is not None:
            junit = next(a for a in cmd if a.startswith("--junitxml="))
            Path(junit.split("=", 1)[1]).write_text(self.report, encoding="utf-8")


def _install(monkeypatch: pytest.MonkeyPatch, runner: _Runner) -> None:
    monkeypatch.setattr(red_check, "_git", runner.git)
    monkeypatch.setattr(subprocess, "run", runner.run)


def test_run_old_runs_whole_files_on_the_base_with_support_copied_in(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = _Runner("<report/>", {"HEAD:tests/helpers.py": "VALUE = 1\n"})
    _install(monkeypatch, runner)
    copied: list[tuple[str, str]] = []
    original = Path.write_text

    def spy(self: Path, data: str, *args: Any, **kwargs: Any) -> int:
        if self.name == "helpers.py":
            copied.append((self.as_posix(), data))
        return original(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", spy)
    report = red_check.run_old(tmp_path, "BASE", ["tests/helpers.py"], ["tests/test_a.py"])
    assert report == "<report/>"
    assert runner.tree is not None
    assert copied == [((runner.tree / "tests/helpers.py").as_posix(), "VALUE = 1\n")]
    assert runner.git_calls[0][:3] == ("worktree", "add", "--detach")
    assert runner.git_calls[0][4] == "BASE"
    assert ("show", "HEAD:tests/helpers.py") in runner.git_calls
    cmd, kwargs = runner.pytest_calls[0]
    assert cmd[1:4] == ["-m", "pytest", "tests/test_a.py"]
    assert cmd[4:8] == ["-q", "-p", "no:cacheprovider", "--continue-on-collection-errors"]
    assert cmd[8].startswith("--junitxml=")
    assert kwargs["cwd"] == runner.tree
    assert kwargs["timeout"] == red_check.PYTEST_TIMEOUT_SECONDS == 600
    assert kwargs["check"] is False
    assert kwargs["capture_output"] is True


def test_run_old_removes_the_worktree_and_the_temporary_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = _Runner("<report/>")
    _install(monkeypatch, runner)
    red_check.run_old(tmp_path, "BASE", [], ["tests/test_a.py"])
    assert runner.tree is not None
    assert runner.git_calls[-1] == ("worktree", "remove", "--force", str(runner.tree))
    assert not runner.tree.parent.exists()


def test_run_old_without_a_report_fails_loudly_and_still_cleans_up(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = _Runner(None)
    _install(monkeypatch, runner)
    with pytest.raises(StateError, match="pytest produced no report on the old code"):
        red_check.run_old(tmp_path, "BASE", [], ["tests/test_a.py"])
    assert runner.tree is not None
    assert runner.git_calls[-1][:2] == ("worktree", "remove")
    assert not runner.tree.parent.exists()


# ------------------------------------------------------------------------------- main


class _Repo:
    """A fake git history for main(): merge base, changed files and file contents."""

    def __init__(
        self,
        changed: list[str],
        old: dict[str, str],
        new: dict[str, str],
        task_files: dict[str, str] | None = None,
    ) -> None:
        self.changed = changed
        self.old = old
        self.new = new
        self.task_files = task_files or {}

    def git(self, _root: Path, *args: str) -> str:
        if args[0] == "merge-base":
            return "MERGEBASE\n"
        if args[0] == "diff":
            if args[-1] == "state/tasks":
                return "\n".join(self.task_files)
            return "\n".join(self.changed)
        assert args[0] == "show"
        ref, path = args[1].split(":", 1)
        if path in self.task_files:
            return self.task_files[path]
        table = self.old if ref == "MERGEBASE" else self.new
        if path not in table:
            raise StateError(f"git show {args[1]} failed: missing")
        return table[path]


TEST_SOURCE = "def test_one():\n    assert False\n\n\ndef test_two():\n    assert False\n"
ARGS = ["--root", ".", "--base", "origin/main"]


def _patch_main(
    monkeypatch: pytest.MonkeyPatch, repo: _Repo, report: str | None
) -> list[tuple[str, list[str], list[str]]]:
    runs: list[tuple[str, list[str], list[str]]] = []

    def fake_run_old(_root: Path, base: str, support: list[str], files: list[str]) -> str:
        runs.append((base, support, files))
        if report is None:
            raise StateError("pytest produced no report on the old code")
        return report

    monkeypatch.setattr(red_check, "_git", repo.git)
    monkeypatch.setattr(red_check, "run_old", fake_run_old)
    return runs


def _case(name: str, bad: bool) -> str:
    inner = '<failure message="f"/>' if bad else ""
    return f'<testcase classname="tests.test_a" name="{name}">{inner}</testcase>'


def test_main_ok_when_every_added_test_fails_on_the_old_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = _Repo(
        ["tests/test_a.py", "tests/helpers.py", "src/app.py", "README.md"],
        old={},
        new={"tests/test_a.py": TEST_SOURCE, "tests/helpers.py": "X = 1\n"},
    )
    report = _report(_case("test_one", True), _case("test_two", True))
    runs = _patch_main(monkeypatch, repo, report)
    assert red_check.main(ARGS) == 0
    out = capsys.readouterr()
    assert out.out == "OK: 2 added tests failed on the old code.\n"
    assert out.err == ""
    # Support files are every changed .py under a test prefix; sources outside it are not copied.
    assert runs == [("MERGEBASE", ["tests/helpers.py", "tests/test_a.py"], ["tests/test_a.py"])]


def test_main_uses_the_singular_for_one_added_test(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = _Repo(
        ["tests/test_a.py"],
        old={"tests/test_a.py": "def test_one():\n    assert False\n"},
        new={"tests/test_a.py": TEST_SOURCE},
    )
    _patch_main(monkeypatch, repo, _report(_case("test_two", True)))
    assert red_check.main(ARGS) == 0
    assert capsys.readouterr().out == "OK: 1 added test failed on the old code.\n"


def test_main_returns_1_and_names_a_test_that_passes_on_the_old_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = _Repo(["tests/test_a.py"], old={}, new={"tests/test_a.py": TEST_SOURCE})
    _patch_main(monkeypatch, repo, _report(_case("test_one", True), _case("test_two", False)))
    assert red_check.main(ARGS) == 1
    out = capsys.readouterr()
    assert out.err == (
        "PROBLEM: tests/test_a.py::test_two passes on the old code; it did not drive the change\n"
    )
    assert out.out == ""


def test_main_returns_2_when_an_added_test_did_not_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = _Repo(["tests/test_a.py"], old={}, new={"tests/test_a.py": TEST_SOURCE})
    _patch_main(monkeypatch, repo, _report(_case("test_one", True)))
    assert red_check.main(ARGS) == 2
    assert (
        capsys.readouterr().err == "ERROR: tests/test_a.py::test_two did not run on the old code\n"
    )


def test_main_missing_takes_precedence_over_passing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = _Repo(["tests/test_a.py"], old={}, new={"tests/test_a.py": TEST_SOURCE})
    _patch_main(monkeypatch, repo, _report(_case("test_one", False)))
    assert red_check.main(ARGS) == 2
    err = capsys.readouterr().err
    assert "did not run on the old code" in err
    assert "PROBLEM" not in err


def test_main_returns_2_with_the_message_of_a_state_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = _Repo(["tests/test_a.py"], old={}, new={"tests/test_a.py": TEST_SOURCE})
    _patch_main(monkeypatch, repo, None)
    assert red_check.main(ARGS) == 2
    assert capsys.readouterr().err == "ERROR: pytest produced no report on the old code\n"


def test_main_returns_2_when_git_cannot_find_the_merge_base(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def failing(_root: Path, *args: str) -> str:
        raise StateError(f"git {' '.join(args)} failed: boom")

    monkeypatch.setattr(red_check, "_git", failing)
    assert red_check.main(["--base", "nope"]) == 2
    assert capsys.readouterr().err == "ERROR: git merge-base nope HEAD failed: boom\n"


def test_main_skips_and_prints_the_declaration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    task = json.dumps({"id": "task_009", "type": "refactor"})
    repo = _Repo(
        ["tests/test_a.py"],
        old={},
        new={"tests/test_a.py": TEST_SOURCE},
        task_files={"state/tasks/task_009.json": task},
    )
    runs = _patch_main(monkeypatch, repo, None)
    assert red_check.main(ARGS) == 0
    assert capsys.readouterr().out == "SKIPPED: task_009 declares type refactor\n"
    assert runs == []


def test_main_excludes_and_prints_characterization_tests(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    source = (
        "import pytest\n\n\n"
        '@pytest.mark.characterization(reason="already guarded")\n'
        "def test_known():\n    assert True\n\n\n"
        "def test_new():\n    assert False\n"
    )
    repo = _Repo(["tests/test_a.py"], old={}, new={"tests/test_a.py": source})
    _patch_main(monkeypatch, repo, _report(_case("test_new", True)))
    assert red_check.main(ARGS) == 0
    assert capsys.readouterr().out == (
        "DECLARED characterization: tests/test_a.py::test_known: already guarded\n"
        "OK: 1 added test failed on the old code.\n"
    )


def test_main_with_only_characterization_tests_has_nothing_to_check(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    source = (
        "import pytest\n\n\n"
        '@pytest.mark.characterization(reason="r")\n'
        "def test_known():\n    assert True\n"
    )
    repo = _Repo(["tests/test_a.py"], old={}, new={"tests/test_a.py": source})
    runs = _patch_main(monkeypatch, repo, None)
    assert red_check.main(ARGS) == 0
    assert capsys.readouterr().out == (
        "DECLARED characterization: tests/test_a.py::test_known: r\nOK: no added tests to check.\n"
    )
    assert runs == []


def test_main_without_test_changes_has_nothing_to_check(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = _Repo(["src/app.py", "tests/helpers.py"], old={}, new={})
    runs = _patch_main(monkeypatch, repo, None)
    assert red_check.main(ARGS) == 0
    assert capsys.readouterr().out == "OK: no added tests to check.\n"
    assert runs == []


def test_main_requires_a_base() -> None:
    with pytest.raises(SystemExit) as info:
        red_check.main([])
    assert info.value.code == 2
