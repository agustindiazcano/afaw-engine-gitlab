"""Tests for the Claude Code hooks: the safety guard and the session-start context."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / ".claude" / "hooks" / "safety_guard.py"
SESSION = REPO_ROOT / ".claude" / "hooks" / "session_start.py"


def guard(tool: str, **tool_input: str) -> tuple[str, str]:
    """Run the guard on one tool call and return (decision, reason)."""
    payload = json.dumps({"tool_name": tool, "tool_input": tool_input})
    result = subprocess.run(
        [sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, timeout=30
    )
    out = json.loads(result.stdout)
    if not out:
        return "allow", ""
    decision = out["hookSpecificOutput"]
    return decision["permissionDecision"], decision["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command",
    [
        "rm PENDING.md",
        "git rm PENDING.md",
        "echo '' > PENDING.md",
        "git push origin main",
        "git push origin HEAD:main",
        "git push -u origin main",
        "echo '{}' > state/equivalent_mutants.json",
        "rm build/state/context/global/LASTCONTEXT.md",
    ],
)
def test_hard_denied_commands(command: str) -> None:
    assert guard("Bash", command=command)[0] == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "DELETE FROM orders",
        "psql -c 'DROP TABLE orders'",
        "git push --force origin feat/x",
        "git reset --hard HEAD~1",
        "git clean -fd",
        "git restore .",
        "gh pr merge 12",
        "docker compose down -v",
    ],
)
def test_destructive_commands_ask(command: str) -> None:
    assert guard("Bash", command=command)[0] == "ask"


@pytest.mark.characterization(
    reason="the v1.0 guard already allowed ordinary commands; kept as a regression test"
)
@pytest.mark.parametrize(
    "command",
    [
        "git push -u origin feat/maintenance-page",
        "git status",
        "python -m pytest tests/tooling/test_model.py::test_invalid_owner",
        "cat PENDING.md",
        "DELETE FROM orders WHERE id = 3",
    ],
)
def test_ordinary_commands_allowed(command: str) -> None:
    assert guard("Bash", command=command)[0] == "allow"


@pytest.mark.parametrize(
    "path",
    ["state/equivalent_mutants.json", "/repo/build/state/pending.json", "build/facts.json"],
)
def test_agent_cannot_write_human_or_generated_files(path: str) -> None:
    assert guard("Write", file_path=path)[0] == "deny"


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "config/.env.prod",
        "migrations/0003_drop.py",
        "alembic/versions/a1.py",
        ".github/workflows/checks.yml",
        "state/config.json",
        "CODEOWNERS",
    ],
)
def test_protected_files_ask(path: str) -> None:
    assert guard("Edit", file_path=path)[0] == "ask"


@pytest.mark.characterization(
    reason="the v1.0 guard already allowed ordinary files; kept as a regression test"
)
def test_ordinary_file_allowed() -> None:
    assert guard("Edit", file_path="src/back/orders.py")[0] == "allow"


@pytest.mark.characterization(
    reason="the v1.0 guard already ignored invalid payloads; kept as a regression test"
)
def test_unparseable_payload_is_allowed_silently() -> None:
    result = subprocess.run(
        [sys.executable, str(GUARD)], input="not json", capture_output=True, text=True, timeout=30
    )
    assert result.stdout.strip() == "{}"


def _session(project: Path, runner: str) -> dict[str, str]:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project), "AFAW_BUILD_COMMAND": runner}
    result = subprocess.run(
        [sys.executable, str(SESSION)], capture_output=True, text=True, timeout=60, env=env
    )
    context: str = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    return {"context": context}


def test_session_start_injects_generated_lastcontext_and_pending(tmp_path: Path) -> None:
    (tmp_path / "PENDING.md").write_text("# Roadmap\n- ship v1.1\n", encoding="utf-8")
    view = tmp_path / "build/state/context/global/LASTCONTEXT.md"
    python = Path(sys.executable).as_posix()
    runner = (
        f"{python} -c \"import pathlib; p = pathlib.Path(r'{view.as_posix()}'); "
        "p.parent.mkdir(parents=True, exist_ok=True); p.write_text('# Last context\\nok\\n')\""
    )
    context = _session(tmp_path, runner)["context"]
    assert "## LASTCONTEXT.md (generated from origin/main)" in context
    assert "# Last context\nok" in context
    assert "## PENDING.md" in context and "ship v1.1" in context


def test_session_start_reports_a_failed_build_instead_of_stale_context(tmp_path: Path) -> None:
    stale = tmp_path / "build/state/context/global/LASTCONTEXT.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("# Last context\nSTALE\n", encoding="utf-8")
    python = Path(sys.executable).as_posix()
    runner = f"{python} -c \"import sys; sys.stderr.write('bad task file'); sys.exit(1)\""
    context = _session(tmp_path, runner)["context"]
    assert "could not build the derived views" in context
    assert "bad task file" in context
    assert "STALE" not in context


def _git_project(project: Path) -> str:
    """Make ``project`` a git repo whose origin/main is one empty commit; return its sha."""
    def git(*args: str) -> str:
        done = subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            cwd=project, check=True, capture_output=True, text=True, timeout=30,
        )
        return done.stdout.strip()

    git("init", "-b", "main")
    git("commit", "--allow-empty", "-m", "first")
    sha = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/main", sha)
    return sha


def _handoff(project: Path, main_sha: str) -> None:
    target = project / "state/handoff/HANDOFF.md"
    target.parent.mkdir(parents=True)
    target.write_text(
        f"# Handoff\n\n## Written at\n- Commit: `{main_sha}`\n- Main: `{main_sha}`\n"
        "\n## What is done, what is next\nFINISH THE HOOK\n",
        encoding="utf-8",
    )


def _ok_runner(project: Path) -> str:
    view = project / "build/state/context/global/LASTCONTEXT.md"
    python = Path(sys.executable).as_posix()
    return (
        f"{python} -c \"import pathlib; p = pathlib.Path(r'{view.as_posix()}'); "
        "p.parent.mkdir(parents=True, exist_ok=True); p.write_text('# Last context\\nok\\n')\""
    )


def test_session_start_prints_the_handoff_file(tmp_path: Path) -> None:
    sha = _git_project(tmp_path)
    _handoff(tmp_path, sha)
    context = _session(tmp_path, _ok_runner(tmp_path))["context"]
    assert "## HANDOFF.md" in context and "FINISH THE HOOK" in context
    assert "main has moved" not in context


def test_session_start_is_silent_without_a_handoff_file(tmp_path: Path) -> None:
    _git_project(tmp_path)
    context = _session(tmp_path, _ok_runner(tmp_path))["context"]
    assert "HANDOFF" not in context


def test_session_start_warns_when_main_moved_since_the_handoff(tmp_path: Path) -> None:
    sha = _git_project(tmp_path)
    _handoff(tmp_path, "0" * 40)
    context = _session(tmp_path, _ok_runner(tmp_path))["context"]
    assert "FINISH THE HOOK" in context
    assert "main has moved" in context and sha[:8] in context
