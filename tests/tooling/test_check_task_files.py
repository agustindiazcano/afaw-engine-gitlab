import json
import subprocess

import pytest

from scripts import check_task_files
from scripts.check_task_files import check
from tests.tooling.helpers import make_task


def fake(diff, base_files, head_files):
    def run(args):
        if args[0] == "diff":
            return diff
        if args[0] == "show":
            import subprocess

            path = args[1].split(":", 1)[1]
            if path not in base_files:
                raise subprocess.CalledProcessError(128, "git show")
            return json.dumps(base_files[path])
        raise AssertionError(args)

    return run, lambda path: json.dumps(head_files[path])


P1 = "state/tasks/task_001.json"


def test_valid_change_passes():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="in_progress", branch="feat/x")},
    )
    assert check("base", "feat/x", run, read) == []


def test_deletion_rejected():
    run, read = fake(f"D\t{P1}\n", {}, {})
    assert "never deleted" in check("base", None, run, read)[0]


def test_forbidden_transition_rejected():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="done", branch="feat/x")},
        {P1: make_task(status="in_progress", branch="feat/x")},
    )
    assert any(
        "status change not allowed: done -> in_progress" in e
        for e in check("base", "feat/x", run, read)
    )


def test_new_task_cannot_start_cancelled():
    run, read = fake(f"A\t{P1}\n", {}, {P1: make_task(status="cancelled")})
    assert any("cannot start as cancelled" in e for e in check("base", "feat/x", run, read))


def test_single_pull_request_task_goes_from_pending_to_done():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="done", branch="feat/x")},
    )
    assert check("base", "feat/x", run, read) == []


def test_derived_field_rejected():
    run, read = fake(f"A\t{P1}\n", {}, {P1: make_task(merged_at="2026-09-01T00:00:00Z")})
    assert any("derived field" in e for e in check("base", None, run, read))


def test_id_must_match_file_name():
    run, read = fake(f"A\t{P1}\n", {}, {P1: make_task("task_002")})
    assert any("does not match the file name" in e for e in check("base", None, run, read))


def test_branch_must_be_the_pull_request_branch():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="in_progress", branch="feat/other")},
    )
    assert any("is not this pull request's branch" in e for e in check("base", "feat/x", run, read))


def test_a_mirror_pull_request_may_carry_tasks_of_other_branches():
    # sync/* pull requests copy what GitLab already merged: several tasks, each with its own branch
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="done", branch="feat/other")},
    )
    assert check("base", "sync/gitlab-main", run, read) == []


def test_a_mirror_pull_request_is_still_held_to_every_other_rule():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="done", branch="feat/other")},
        {P1: make_task(status="in_progress", branch="feat/other")},  # done is final
    )
    errors = check("base", "sync/gitlab-main", run, read)
    assert errors and not any("is not this pull request's branch" in e for e in errors)


@pytest.mark.characterization(reason="the rule already applies to every other branch name")
def test_only_the_sync_prefix_is_a_mirror():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="done", branch="feat/other")},
    )
    for name in ("feat/sync/x", "synchronize", "sync"):
        assert any("is not this pull request's branch" in e for e in check("base", name, run, read))


def test_human_task_is_not_bound_to_the_branch():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending", owner="human")},
        {P1: make_task(status="done", owner="human")},
    )
    assert check("base", "feat/x", run, read) == []


def test_owner_and_status_cannot_change_together():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="done", owner="human")},
    )
    assert any(
        "owner and status cannot change in the same pull request" in e
        for e in check("base", "feat/x", run, read)
    )


def test_new_task_id_must_not_exist_on_the_target_branch():
    # Two parallel branches may pick the same next id; the second one to merge must rename.
    base_run, read = fake(f"A\t{P1}\n", {}, {P1: make_task()})

    def run(args):
        if args[0] == "cat-file":
            return ""  # exists on origin/main
        return base_run(args)

    errors = check("base", None, run, read, target="origin/main")
    assert errors == [
        f"{P1}: task id task_001 already exists on origin/main; pick the next free id"
    ]


def test_a_copy_identical_to_the_target_is_not_a_change():
    # A branch can carry task files of main without its history (a merge with one parent):
    # against the merge base they look new, but merging them changes nothing on the target.
    task = make_task(status="in_progress", branch="docs/other")

    def run(args):
        if args[0] == "diff":
            return f"A\t{P1}\n"
        if args[0] == "cat-file":
            return ""  # exists on origin/main
        if args[0] == "show" and args[1] == f"origin/main:{P1}":
            return json.dumps(task)
        raise subprocess.CalledProcessError(128, "git show")

    errors = check("base", "feat/x", run, lambda path: json.dumps(task), target="origin/main")
    assert errors == []


@pytest.mark.characterization(
    reason="a differing copy was always checked; the test pins that the skip stays narrow"
)
def test_a_task_that_differs_from_the_target_is_still_checked():
    on_target = make_task(status="in_progress", branch="docs/other")
    on_branch = make_task(status="in_progress", branch="docs/other", title="Another task")

    def run(args):
        if args[0] == "diff":
            return f"A\t{P1}\n"
        if args[0] == "cat-file":
            return ""
        if args[0] == "show" and args[1] == f"origin/main:{P1}":
            return json.dumps(on_target)
        raise subprocess.CalledProcessError(128, "git show")

    errors = check("base", "feat/x", run, lambda path: json.dumps(on_branch), target="origin/main")
    assert any("already exists on origin/main" in e for e in errors)


def test_v1_0_task_file_migrates_without_reopening():
    # v1.0 used status "completed" and a free-text owner; the migrated file is the same task.
    old = {"id": "task_001", "status": "completed", "owner": "antigravity", "locked_files": []}
    new = make_task(status="done", branch="chore/fix-role-typo", type="chore")
    run, read = fake(f"M\t{P1}\n", {P1: old}, {P1: new})
    assert check("base", "feat/migration", run, read) == []


# --- more rules of check() and its helpers -------------------------------------------------


def raw_fake(diff, base_texts, head_texts, existing=()):
    """Like ``fake`` but base and head hold raw text, so invalid JSON can be served."""

    def run(args):
        if args[0] == "diff":
            return diff
        if args[0] == "show":
            path = args[1].split(":", 1)[1]
            if path not in base_texts:
                raise subprocess.CalledProcessError(128, "git show")
            return base_texts[path]
        if args[0] == "cat-file":
            if args[2].split(":", 1)[1] not in existing:
                raise subprocess.CalledProcessError(128, "git cat-file")
            return ""
        raise AssertionError(args)

    return run, lambda path: head_texts[path]


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_files_that_are_not_json_are_ignored():
    run, read = raw_fake("A\tstate/tasks/README.md\nD\tstate/tasks/notes.txt\n", {}, {})
    assert check("base", None, run, read) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_invalid_json_in_the_head_file_is_reported_and_checking_continues():
    run, read = raw_fake(f"A\t{P1}\n", {}, {P1: "{broken"})
    errors = check("base", "feat/x", run, read)
    assert len(errors) == 1
    assert errors[0].startswith(f"{P1}: not valid JSON: ")


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_a_task_file_that_is_not_an_object_is_reported_once():
    run, read = raw_fake(f"A\t{P1}\n", {}, {P1: "[1, 2]"})
    assert check("base", None, run, read) == [f"{P1}: task file must be a JSON object"]


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_a_missing_target_id_check_is_skipped_without_a_target():
    run, read = raw_fake(f"A\t{P1}\n", {}, {P1: json.dumps(make_task())}, existing={P1})
    assert check("base", None, run, read) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_new_task_with_a_free_id_passes_the_target_check():
    run, read = raw_fake(f"A\t{P1}\n", {}, {P1: json.dumps(make_task())})
    assert check("base", None, run, read, target="origin/main") == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_target_is_checked_for_added_files_only():
    run, read = raw_fake(
        f"M\t{P1}\n",
        {P1: json.dumps(make_task(status="pending"))},
        {P1: json.dumps(make_task(status="pending"))},
        existing={P1},
    )
    assert check("base", None, run, read, target="origin/main") == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_unchanged_status_on_a_modified_task_is_allowed():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="pending", title="New title")},
    )
    assert check("base", "feat/x", run, read) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_unreadable_base_file_is_treated_as_a_new_task():
    # git show fails on the base: no previous status, so "cancelled" is rejected as a start state
    run, read = fake(f"M\t{P1}\n", {}, {P1: make_task(status="cancelled")})
    assert any("cannot start as cancelled" in e for e in check("base", None, run, read))


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_invalid_json_on_the_base_side_is_treated_as_unreadable():
    run, read = raw_fake(
        f"M\t{P1}\n", {P1: "not json"}, {P1: json.dumps(make_task(status="cancelled"))}
    )
    assert any("cannot start as cancelled" in e for e in check("base", None, run, read))


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_base_file_that_is_not_an_object_is_treated_as_unreadable():
    run, read = raw_fake(f"M\t{P1}\n", {P1: "[1]"}, {P1: json.dumps(make_task(status="cancelled"))})
    assert any("cannot start as cancelled" in e for e in check("base", None, run, read))


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_base_with_a_non_string_status_is_reported_as_invalid():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: {"id": "task_001", "status": 7, "owner": "agent"}},
        {P1: make_task(status="pending")},
    )
    assert check("base", None, run, read) == [f"{P1}: invalid status: 7"]


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_base_without_an_owner_defaults_to_agent():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: {"id": "task_001", "status": "pending"}},
        {P1: make_task(status="done", owner="human")},
    )
    assert any("owner and status cannot change" in e for e in check("base", None, run, read))


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_base_with_an_unknown_owner_skips_the_owner_rule():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: {"id": "task_001", "status": "pending", "owner": "antigravity"}},
        {P1: make_task(status="done", owner="human")},
    )
    assert check("base", None, run, read) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_owner_change_with_the_same_status_is_allowed():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="pending", owner="human")},
    )
    assert check("base", None, run, read) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_legacy_blocked_status_reads_as_pending():
    old = {"id": "task_001", "status": "blocked", "owner": "agent"}
    run, read = fake(f"M\t{P1}\n", {P1: old}, {P1: make_task(status="backlog")})
    assert check("base", None, run, read) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_agent_task_that_stays_done_may_keep_another_branch():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="done", branch="feat/old")},
        {P1: make_task(status="done", branch="feat/old", title="Typo")},
    )
    assert check("base", "feat/x", run, read) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_without_a_head_branch_the_branch_rule_is_skipped():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="in_progress", branch="feat/other")},
    )
    assert check("base", None, run, read) == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_branch_error_message_names_both_branches():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="in_progress", branch="feat/other")},
    )
    assert check("base", "feat/x", run, read) == [
        f"{P1}: branch 'feat/other' is not this pull request's branch 'feat/x'"
    ]


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_several_changed_files_are_all_checked():
    p2 = "state/tasks/task_002.json"
    run, read = raw_fake(
        f"D\t{P1}\nA\t{p2}\n",
        {},
        {p2: json.dumps(make_task("task_003"))},
    )
    errors = check("base", None, run, read)
    assert errors == [
        f"{P1}: task files are never deleted; set the status to cancelled",
        f"{p2}: id 'task_003' does not match the file name",
    ]


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_diff_is_requested_between_base_and_head_for_the_task_folder():
    seen = []

    def run(args):
        seen.append(args)
        return ""

    assert check("abc", None, run, lambda p: "") == []
    assert seen == [["diff", "--name-status", "--no-renames", "abc", "HEAD", "--", "state/tasks/"]]


# --- main() --------------------------------------------------------------------------------


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_main_passes_its_arguments_to_check_and_reports_ok(monkeypatch, capsys):
    captured = {}

    def fake_check(base, head_branch, run, read_head, target):
        captured.update(base=base, head_branch=head_branch, run=run, target=target)
        return []

    monkeypatch.setattr(check_task_files, "check", fake_check)
    code = check_task_files.main(
        ["--base", "abc", "--head-branch", "feat/x", "--target", "origin/main"]
    )
    out = capsys.readouterr()
    assert code == 0
    assert out.out == "OK: task file check passed (0 task files checked).\n"
    assert out.err == ""
    assert captured["base"] == "abc"
    assert captured["head_branch"] == "feat/x"
    assert captured["target"] == "origin/main"
    assert captured["run"] is check_task_files.git_runner


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_main_defaults_head_branch_and_target_to_none(monkeypatch):
    captured = {}

    def fake_check(base, head_branch, run, read_head, target):
        captured.update(head_branch=head_branch, target=target)
        return []

    monkeypatch.setattr(check_task_files, "check", fake_check)
    assert check_task_files.main(["--base", "abc"]) == 0
    assert captured == {"head_branch": None, "target": None}


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_main_lists_every_problem_on_stderr_and_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(check_task_files, "check", lambda *a, **k: ["first", "second"])
    code = check_task_files.main(["--base", "abc"])
    out = capsys.readouterr()
    assert code == 1
    assert out.err == "PROBLEM: first\nPROBLEM: second\n"
    assert out.out == ""


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_main_requires_a_base(capsys):
    with pytest.raises(SystemExit) as exc:
        check_task_files.main([])
    assert exc.value.code == 2
    assert "--base" in capsys.readouterr().err


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_main_reads_head_files_from_the_working_tree(monkeypatch, tmp_path):
    (tmp_path / "t.json").write_text('{"ünï": 1}', encoding="utf-8")
    read = {}

    def fake_check(base, head_branch, run, read_head, target):
        read["text"] = read_head(str(tmp_path / "t.json"))
        return []

    monkeypatch.setattr(check_task_files, "check", fake_check)
    check_task_files.main(["--base", "abc"])
    assert read["text"] == '{"ünï": 1}'


def test_main_reports_how_many_task_files_the_check_read(monkeypatch, capsys):
    def fake_check(base, head_branch, run, read_head, target):
        read_head("state/tasks/task_001.json")
        read_head("state/tasks/task_002.json")
        read_head("state/tasks/task_003.json")
        return []

    monkeypatch.setattr(check_task_files, "check", fake_check)
    monkeypatch.setattr(check_task_files.Path, "read_text", lambda self, encoding: "{}")
    code = check_task_files.main(["--base", "abc"])
    out = capsys.readouterr()
    assert code == 0
    assert out.out == "OK: task file check passed (3 task files checked).\n"
