"""request_fix: a failed pipeline asks the Duo Developer Flow to repair it, with a cap of 3."""

from __future__ import annotations

from typing import Any

import pytest

from scripts import request_fix
from scripts.afaw_state.facts import FactsError
from scripts.request_fix import (
    CAP,
    FLOW_USERNAME,
    GLOBAL_CAP,
    LABEL,
    failing_jobs,
    log_tail,
    marker_for_ref,
    marker_for_sha,
)

SHA = "0123456789abcdef0123456789abcdef01234567"
SHA8 = SHA[:8]
ENV_MR = {
    "CI_PIPELINE_ID": "10",
    "CI_COMMIT_SHA": SHA,
    "CI_MERGE_REQUEST_IID": "7",
    "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME": "feat/x",
    "CI_DEFAULT_BRANCH": "main",
    "CI_PIPELINE_SOURCE": "merge_request_event",
}
ENV_BRANCH = {
    "CI_PIPELINE_ID": "10",
    "CI_COMMIT_SHA": SHA,
    "CI_COMMIT_REF_NAME": "demo/lint",
    "CI_DEFAULT_BRANCH": "main",
    "CI_PIPELINE_SOURCE": "push",
}


def job(name: str, status: str = "success", **extra: Any) -> dict[str, Any]:
    return {"id": hash(name) % 1000, "name": name, "stage": "verify", "status": status, **extra}


class FakeApi:
    def __init__(self, jobs, notes=None, issues=None, traces=None):
        self.jobs = jobs
        self.notes = notes or []
        self.issues = issues or []
        self.traces = traces or {}
        self.posted: list[tuple[int, str]] = []
        self.created: list[dict[str, Any]] = []

    def pipeline_jobs(self, pipeline_id):
        return self.jobs

    def job_trace(self, job_id):
        return self.traces.get(job_id, "line one\nline two\n")

    def mr_notes(self, iid):
        return self.notes

    def labeled_issues(self, label):
        return self.issues

    def user_id(self, username):
        assert username == FLOW_USERNAME
        return 33073386

    def post_note(self, iid, body):
        self.posted.append((iid, body))

    def create_issue(self, title, description, assignee_id, label):
        self.created.append(
            {"title": title, "description": description, "assignee": assignee_id, "label": label}
        )


# ------------------------------------------------------------------ what failed


def test_only_failed_jobs_count_and_the_guards_own_jobs_are_ignored():
    jobs = [
        job("lint", "failed"),
        job("red_check", "success"),
        job("merge_guard", "failed"),
        job("request_fix", "failed"),
        job("semgrep", "failed", allow_failure=True),
    ]
    assert [j["name"] for j in failing_jobs(jobs)] == ["lint"]


def test_the_log_tail_drops_colour_codes_section_markers_and_blank_lines():
    trace = (
        "section_start:1:step_script\r\x1b[0K\x1b[32;1m$ ruff check\x1b[0;m\n"
        "\n"
        "F401 unused import\n"
        "section_end:2:step_script\r\x1b[0K\n"
    )
    assert log_tail(trace) == "$ ruff check\nF401 unused import"


def test_the_log_tail_keeps_the_end_and_is_bounded():
    trace = "\n".join(f"line {i}" for i in range(500))
    tail = log_tail(trace)
    assert tail.endswith("line 499") and "line 0" not in tail
    assert len(tail) <= 1500


# ------------------------------------------------------------------ a merge request


def test_a_failed_merge_request_pipeline_gets_one_note_that_mentions_the_flow():
    api = FakeApi([job("lint", "failed"), job("red_check")], traces={})
    assert request_fix.run(api, ENV_MR) == 0
    assert len(api.posted) == 1
    iid, body = api.posted[0]
    assert iid == 7
    assert f"@{FLOW_USERNAME}" in body
    assert "`lint`" in body and "line two" in body
    assert marker_for_sha(SHA8) in body
    assert f"attempt 1 of {CAP}" in body


def test_the_same_commit_is_never_asked_twice():
    api = FakeApi([job("lint", "failed")], notes=[{"body": f"x {marker_for_sha(SHA8)}"}])
    assert request_fix.run(api, ENV_MR) == 0
    assert api.posted == []


def test_the_cap_of_attempts_stops_the_requests(capsys):
    notes = [{"body": marker_for_sha(f"deadbee{i}")} for i in range(CAP)]
    api = FakeApi([job("lint", "failed")], notes=notes)
    assert request_fix.run(api, ENV_MR) == 0
    assert api.posted == []
    assert f"cap of {CAP}" in capsys.readouterr().out


def test_a_second_attempt_says_so():
    api = FakeApi([job("lint", "failed")], notes=[{"body": marker_for_sha("deadbeef")}])
    request_fix.run(api, ENV_MR)
    assert f"attempt 2 of {CAP}" in api.posted[0][1]


def test_a_green_pipeline_asks_for_nothing(capsys):
    api = FakeApi([job("lint"), job("red_check")])
    assert request_fix.run(api, ENV_MR) == 0
    assert api.posted == [] and api.created == []


# ------------------------------------------------------------------ a branch with no merge request


def test_a_failed_branch_with_no_merge_request_opens_an_issue_for_the_flow():
    api = FakeApi([job("lint", "failed")])
    assert request_fix.run(api, ENV_BRANCH) == 0
    assert len(api.created) == 1
    issue = api.created[0]
    assert issue["title"] == f"autoheal: lint @ {SHA8}"
    assert issue["assignee"] == 33073386 and issue["label"] == LABEL
    assert "demo/lint" in issue["description"]
    assert marker_for_ref("demo/lint") in issue["description"]
    assert "line two" in issue["description"]


def test_an_open_issue_for_the_same_failure_is_not_duplicated():
    api = FakeApi([job("lint", "failed")], issues=[{"title": f"autoheal: lint @ {SHA8}"}])
    assert request_fix.run(api, ENV_BRANCH) == 0
    assert api.created == []


def test_the_cap_counts_the_issues_of_the_branch(capsys):
    issues = [
        {"title": f"autoheal: lint @ aaaa000{i}", "description": marker_for_ref("demo/lint")}
        for i in range(CAP)
    ]
    api = FakeApi([job("lint", "failed")], issues=issues)
    assert request_fix.run(api, ENV_BRANCH) == 0
    assert api.created == []
    assert f"cap of {CAP}" in capsys.readouterr().out


def test_the_issues_of_other_branches_do_not_count():
    issues = [
        {"title": f"autoheal: lint @ aaaa000{i}", "description": marker_for_ref("other")}
        for i in range(CAP)
    ]
    api = FakeApi([job("lint", "failed")], issues=issues)
    request_fix.run(api, ENV_BRANCH)
    assert len(api.created) == 1


def test_several_failed_jobs_share_one_issue():
    api = FakeApi([job("lint", "failed"), job("red_check", "failed")])
    request_fix.run(api, ENV_BRANCH)
    assert api.created[0]["title"] == f"autoheal: lint, red_check @ {SHA8}"


def test_open_issues_of_any_branch_are_capped_so_a_chain_of_branches_cannot_run_away(capsys):
    issues = [
        {"title": f"autoheal: lint @ bbbb{i:04d}", "description": marker_for_ref(f"b{i}")}
        for i in range(GLOBAL_CAP)
    ]
    api = FakeApi([job("lint", "failed")], issues=issues)
    assert request_fix.run(api, ENV_BRANCH) == 0
    assert api.created == []
    assert f"{GLOBAL_CAP} open autoheal issues" in capsys.readouterr().out


# ---- failing closed and the HTTP edge


def test_an_api_failure_fails_closed(capsys):
    class Broken(FakeApi):
        def pipeline_jobs(self, pipeline_id):
            raise FactsError("GET failed after 4 attempts (HTTP 503)")

    api = Broken([])
    assert request_fix.run(api, ENV_MR) == 2
    assert api.posted == [] and api.created == []
    assert "503" in capsys.readouterr().err


def test_a_missing_pipeline_id_fails_closed():
    api = FakeApi([job("lint", "failed")])
    assert request_fix.run(api, {"CI_COMMIT_SHA": SHA}) == 2
    assert api.posted == []


def test_the_note_is_sent_with_the_token_only_in_a_header():
    sent = {}

    def post(url, headers, body):
        sent.update(url=url, headers=headers, body=body)
        return {}

    api = request_fix.Api(
        "https://gitlab.com/api/v4",
        "88",
        "s3cret",
        get_json=lambda u: [],
        get_text=lambda u: "",
        post=post,
    )
    api.post_note(7, "hello")
    assert sent["url"] == "https://gitlab.com/api/v4/projects/88/merge_requests/7/notes"
    assert sent["headers"]["PRIVATE-TOKEN"] == "s3cret"
    assert sent["body"] == {"body": "hello"}
    assert "s3cret" not in sent["url"]


def test_creating_an_issue_sends_the_label_and_the_assignee():
    sent = {}

    def post(url, headers, body):
        sent.update(url=url, body=body)
        return {}

    api = request_fix.Api(
        "https://gitlab.com/api/v4",
        "88",
        "t",
        get_json=lambda u: [],
        get_text=lambda u: "",
        post=post,
    )
    api.create_issue("autoheal: lint @ abc", "text", 5, LABEL)
    assert sent["url"].endswith("/projects/88/issues")
    assert sent["body"] == {
        "title": "autoheal: lint @ abc",
        "description": "text",
        "assignee_ids": [5],
        "labels": LABEL,
    }


def test_without_a_token_nothing_is_written():
    api = request_fix.Api("https://gitlab.com/api/v4", "88", None, get_json=lambda u: [])
    with pytest.raises(FactsError, match="AFAW_MERGE_TOKEN"):
        api.post_note(7, "x")
    with pytest.raises(FactsError, match="AFAW_MERGE_TOKEN"):
        api.create_issue("t", "d", 1, LABEL)


# ------------------------------------------------------------------ whose branch it is


@pytest.mark.parametrize("ref", ["feat/task-9-x", "fix/task-9-x", "docs/task-9-x", "chore/x"])
def test_a_failure_on_a_branch_named_by_a_person_opens_no_issue(ref, capsys):
    api = FakeApi([job("lint", "failed")])
    assert request_fix.run(api, {**ENV_BRANCH, "CI_COMMIT_REF_NAME": ref}) == 0
    assert api.created == []
    assert "not asked" in capsys.readouterr().out


@pytest.mark.characterization(reason="documents the branches the flow was always asked about")
@pytest.mark.parametrize("ref", ["main", "demo/task-28-lint", "duo/fix/3-x"])
def test_main_planted_demo_and_flow_branches_are_repaired(ref):
    api = FakeApi([job("lint", "failed")])
    assert request_fix.run(api, {**ENV_BRANCH, "CI_COMMIT_REF_NAME": ref}) == 0
    assert len(api.created) == 1
