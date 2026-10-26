"""The handoff file: sections built from facts, secrets refused, nothing written on refusal."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import handoff

FACTS: dict[str, Any] = {
    "commit": "abc1234def5678",
    "branch": "feat/task-128-handoff",
    "main_commit": "0011223344556677",
    "merge_requests": [{"iid": 12, "title": "Add handoff", "web_url": "https://x/mr/12"}],
    "issues": [{"iid": 57, "title": "Write the hand-over file", "web_url": "https://x/i/57"}],
    "pipelines": [{"id": 900, "status": "success"}, {"id": 899, "status": "failed"}],
    "pending": ["- [ ] Task 011: Duo agents", "- [ ] Task 012: guardrails"],
}


def test_build_has_every_section() -> None:
    text = handoff.build(FACTS, "Tests are written; the CLI is next.")
    for heading in (
        "## Written at",
        "## Open merge requests",
        "## Open issues",
        "## Last pipelines of main",
        "## Open items of PENDING.md",
        "## What is done, what is next",
    ):
        assert heading in text
    assert "abc1234def5678" in text and "feat/task-128-handoff" in text
    assert "!12" in text and "Add handoff" in text
    assert "#57" in text and "Write the hand-over file" in text
    assert "900" in text and "success" in text and "899" in text and "failed" in text
    assert "- [ ] Task 012: guardrails" in text
    assert text.rstrip().endswith("Tests are written; the CLI is next.")


def test_build_orders_sections_with_the_note_last() -> None:
    text = handoff.build(FACTS, "note body")
    order = [
        text.index("## Written at"),
        text.index("## Open merge requests"),
        text.index("## Open issues"),
        text.index("## Last pipelines of main"),
        text.index("## Open items of PENDING.md"),
        text.index("## What is done, what is next"),
    ]
    assert order == sorted(order)


def test_build_says_none_for_empty_sections() -> None:
    empty = {**FACTS, "merge_requests": [], "issues": [], "pipelines": [], "pending": []}
    text = handoff.build(empty, "n")
    assert text.count("None.") == 4


def test_build_records_the_main_commit_for_the_staleness_check() -> None:
    assert "Main: `0011223344556677`" in handoff.build(FACTS, "n")


def test_parse_pending_keeps_only_open_top_level_items() -> None:
    pending = (
        "# Roadmap\n"
        "- [x] Task 007: done\n"
        "- [ ] Task 011: open\n"
        "  - [ ] nested open\n"
        "text - [ ] not a list item\n"
        "- [ ] Task 012: also open  \n"
    )
    assert handoff.parse_pending(pending) == ["- [ ] Task 011: open", "- [ ] Task 012: also open"]


@pytest.mark.parametrize(
    "text",
    [
        "token glpat-" + "a1B2c3D4e5F6g7H8i9J0",
        "pushed with ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8",
        "key AKIA" + "IOSFODNN7EXAMPLE",
        "the token is " + "0123456789abcdef" * 2,
        "SECRET=" + "Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MGFiY2RlZg==",
    ],
)
def test_refuse_secrets_raises_on_token_patterns(text: str) -> None:
    with pytest.raises(ValueError) as error:
        handoff.refuse_secrets(text)
    assert text.split()[-1] not in str(error.value)


@pytest.mark.parametrize(
    "text",
    [
        "The token budget is small.",
        "secret detection job passed",
        "commit " + "0123456789abcdef" * 2 + " was merged",
        "secret_detection_pipeline_template_only",
    ],
)
def test_refuse_secrets_allows_ordinary_text(text: str) -> None:
    handoff.refuse_secrets(text)


def test_cli_refuses_a_secret_in_the_note_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(handoff, "gather", lambda root, project: FACTS)
    out = tmp_path / "state/handoff/HANDOFF.md"
    code = handoff.main(["--note", "use glpat-" + "a1B2c3D4e5F6g7H8i9J0", "--out", str(out)])
    assert code == 2
    assert not out.exists()
    assert not out.parent.exists()


def test_cli_writes_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(handoff, "gather", lambda root, project: FACTS)
    out = tmp_path / "state/handoff/HANDOFF.md"
    assert handoff.main(["--note", "Next: wire the hook.", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "## What is done, what is next" in text and "Next: wire the hook." in text


def test_cli_fails_loudly_when_the_facts_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(root: Path, project: str) -> dict[str, Any]:
        raise handoff.HandoffError("GitLab API unreachable")

    monkeypatch.setattr(handoff, "gather", broken)
    out = tmp_path / "HANDOFF.md"
    assert handoff.main(["--note", "n", "--out", str(out)]) == 2
    assert not out.exists()


def test_git_facts_reads_commit_branch_and_main(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            cwd=tmp_path, check=True, capture_output=True, timeout=30,
        )

    git("init", "-b", "work")
    git("commit", "--allow-empty", "-m", "first")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    facts = handoff.git_facts(tmp_path)
    assert facts["branch"] == "work"
    assert len(facts["commit"]) == 40 and facts["main_commit"] == facts["commit"]


def test_gitlab_facts_reads_open_items_and_main_pipelines() -> None:
    seen: list[str] = []

    def get(url: str) -> Any:
        seen.append(url)
        if "/merge_requests" in url:
            return [{"iid": 1, "title": "mr", "web_url": "u"}]
        if "/issues" in url:
            return [{"iid": 2, "title": "is", "web_url": "v"}]
        return [{"id": 7, "status": "success", "ref": "main", "sha": "x"}]

    facts = handoff.gitlab_facts(get, "88052530")
    assert facts["merge_requests"] == [{"iid": 1, "title": "mr", "web_url": "u"}]
    assert facts["issues"] == [{"iid": 2, "title": "is", "web_url": "v"}]
    assert facts["pipelines"] == [{"id": 7, "status": "success"}]
    assert any("state=opened" in u for u in seen)
    assert any("ref=main" in u for u in seen)
