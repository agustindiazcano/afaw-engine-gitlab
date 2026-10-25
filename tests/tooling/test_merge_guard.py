"""Merge guard: the cap of 3 automatic fix attempts and the rule for an automatic merge."""

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import merge_guard
from scripts.afaw_state.facts import FactsError
from scripts.merge_guard import (
    CAP,
    REQUIRED_JOBS,
    fix_attempts,
    merge_verdict,
)

FIXTURES = Path(__file__).parent / "fixtures" / "gitlab"
BOT = 900


def recorded_jobs() -> list[dict[str, Any]]:
    return json.loads((FIXTURES / "pipeline_2985416324_jobs.json").read_text(encoding="utf-8"))


def mr(**changes: Any) -> dict[str, Any]:
    base = {
        "iid": 7,
        "state": "opened",
        "draft": False,
        "target_branch": "main",
        "has_conflicts": False,
        "blocking_discussions_resolved": True,
        "sha": "abc",
    }
    return {**base, **changes}


def pipe(pid, sha, status, created, user=1, source="push"):
    return {
        "id": pid,
        "sha": sha,
        "status": status,
        "created_at": created,
        "source": source,
        "user": {"id": user},
    }


# ------------------------------------------------------------------ fix attempts


def test_a_fix_attempt_is_a_commit_pushed_by_a_bot_after_a_failed_pipeline():
    pipelines = [
        pipe(1, "a", "failed", "2026-10-24T10:00:00Z", user=1),
        pipe(2, "b", "failed", "2026-10-24T10:10:00Z", user=BOT),
        pipe(3, "b", "failed", "2026-10-24T10:11:00Z", user=BOT, source="merge_request_event"),
        pipe(4, "c", "success", "2026-10-24T10:20:00Z", user=BOT),
    ]
    assert fix_attempts(pipelines, {BOT}) == 2  # b and c; two pipelines of b count once


def test_bot_work_before_any_failure_is_not_a_fix_attempt():
    pipelines = [
        pipe(1, "a", "success", "2026-10-24T10:00:00Z", user=BOT),
        pipe(2, "b", "success", "2026-10-24T10:10:00Z", user=BOT),
    ]
    assert fix_attempts(pipelines, {BOT}) == 0


def test_commits_of_a_human_are_never_counted():
    pipelines = [
        pipe(1, "a", "failed", "2026-10-24T10:00:00Z", user=1),
        pipe(2, "b", "failed", "2026-10-24T10:10:00Z", user=1),
    ]
    assert fix_attempts(pipelines, {BOT}) == 0
    assert fix_attempts(pipelines, set()) == 0


def test_a_pipeline_without_a_user_is_not_attributed_to_a_bot():
    pipelines = [
        pipe(1, "a", "failed", "2026-10-24T10:00:00Z"),
        {**pipe(2, "b", "failed", "2026-10-24T10:10:00Z"), "user": None},
    ]
    assert fix_attempts(pipelines, {BOT}) == 0


# ------------------------------------------------------------------ verdict


def verdict(**kw: Any):
    args: dict[str, Any] = {
        "mr": mr(),
        "pipeline": {"sha": "abc"},
        "jobs": recorded_jobs(),
        "attempts": 0,
        "default_branch": "main",
    }
    args.update(kw)
    return merge_verdict(**args)


def test_the_recorded_green_pipeline_of_an_open_merge_request_may_merge():
    v = verdict()
    assert v.merge and v.reasons == []
    assert set(REQUIRED_JOBS) == {"red_check", "mutation_gate", "security_gate"}
    assert CAP == 3


@pytest.mark.parametrize(
    ("change", "text"),
    [
        ({"mr": mr(state="merged")}, "not open"),
        ({"mr": mr(draft=True)}, "draft"),
        ({"mr": mr(target_branch="dev")}, "target"),
        ({"mr": mr(has_conflicts=True)}, "conflicts"),
        ({"mr": mr(blocking_discussions_resolved=False)}, "discussions"),
        ({"pipeline": {"sha": "old"}}, "head"),
        ({"pipeline": None}, "no pipeline"),
        ({"attempts": 4}, "cap"),
    ],
)
def test_each_condition_alone_holds_the_merge(change, text):
    v = verdict(**change)
    assert not v.merge
    assert any(text in reason for reason in v.reasons)


@pytest.mark.parametrize(
    "status", ["failed", "running", "pending", "manual", "skipped", "canceled"]
)
def test_only_a_success_counts_as_green(status):
    jobs = recorded_jobs()
    jobs[0] = {**jobs[0], "status": status}
    v = verdict(jobs=jobs)
    assert not v.merge and any(jobs[0]["name"] in r for r in v.reasons)


def test_a_failed_job_that_is_allowed_to_fail_still_holds_the_merge():
    jobs = recorded_jobs()
    jobs[0] = {**jobs[0], "status": "failed", "allow_failure": True}
    assert not verdict(jobs=jobs).merge


@pytest.mark.parametrize("name", REQUIRED_JOBS)
def test_a_missing_required_job_holds_the_merge(name):
    jobs = [j for j in recorded_jobs() if j["name"] != name]
    v = verdict(jobs=jobs)
    assert not v.merge and any(name in r and "missing" in r for r in v.reasons)


def test_the_guard_does_not_wait_for_itself():
    jobs = recorded_jobs() + [{"name": merge_guard.GUARD_JOB, "status": "running"}]
    assert verdict(jobs=jobs).merge


def test_every_reason_is_reported():
    v = verdict(mr=mr(draft=True, has_conflicts=True), attempts=5)
    assert len(v.reasons) == 3


# ------------------------------------------------------------------ run


class FakeApi:
    def __init__(self, merge_request, pipelines, jobs, fail_on=None):
        self.merge_request = merge_request
        self.pipelines = pipelines
        self.jobs = jobs
        self.fail_on = fail_on
        self.merged: list[tuple[int, str]] = []

    def get_mr(self, iid):
        if self.fail_on == "mr":
            raise FactsError("GET failed after 4 attempts (HTTP 503)")
        return self.merge_request

    def mr_pipelines(self, iid):
        return self.pipelines

    def pipeline(self, pipeline_id):
        return next(p for p in self.pipelines if p["id"] == pipeline_id)

    def pipeline_jobs(self, pipeline_id):
        return self.jobs

    def merge(self, iid, sha):
        self.merged.append((iid, sha))


GREEN = [pipe(10, "abc", "running", "2026-10-24T12:00:00Z", user=1, source="merge_request_event")]
ENV = {"CI_DEFAULT_BRANCH": "main", "AFAW_BOT_USER_IDS": str(BOT)}


def run(api, env=None, capsys=None):
    return merge_guard.run(api, 7, {**ENV, **(env or {})})


def test_a_green_merge_request_is_reported_but_not_merged_without_the_switch(capsys):
    api = FakeApi(mr(), GREEN, recorded_jobs())
    assert run(api) == 0
    out = capsys.readouterr().out
    assert "merge: yes" in out and "AFAW_AUTO_MERGE" in out
    assert api.merged == []


def test_the_switch_merges_the_exact_head_commit(capsys):
    api = FakeApi(mr(), GREEN, recorded_jobs())
    assert run(api, {"AFAW_AUTO_MERGE": "true"}) == 0
    assert api.merged == [(7, "abc")]


@pytest.mark.parametrize("value", ["", "yes", "1", "True", "TRUE", "false"])
def test_only_the_exact_word_true_turns_the_merge_on(value):
    api = FakeApi(mr(), GREEN, recorded_jobs())
    run(api, {"AFAW_AUTO_MERGE": value})
    assert api.merged == []


def test_a_hold_never_merges_and_lists_the_reasons(capsys):
    api = FakeApi(mr(draft=True), GREEN, recorded_jobs())
    assert run(api, {"AFAW_AUTO_MERGE": "true"}) == 0
    assert api.merged == []
    assert "merge: no" in capsys.readouterr().out


def test_exceeding_the_cap_fails_the_job(capsys):
    pipelines = [pipe(1, "a", "failed", "2026-10-24T10:00:00Z")] + [
        pipe(i + 2, f"s{i}", "failed", f"2026-10-24T10:{i + 1:02d}:00Z", user=BOT) for i in range(4)
    ]
    api = FakeApi(mr(sha="s3"), pipelines, recorded_jobs())
    assert run(api, {"AFAW_AUTO_MERGE": "true"}) == 1
    assert api.merged == []
    assert "4 automatic fix attempts" in capsys.readouterr().out


def test_three_attempts_are_still_within_the_cap():
    pipelines = [pipe(1, "a", "failed", "2026-10-24T10:00:00Z")] + [
        pipe(i + 2, f"s{i}", "failed", f"2026-10-24T10:{i + 1:02d}:00Z", user=BOT) for i in range(3)
    ]
    api = FakeApi(mr(sha="s2"), pipelines, recorded_jobs())
    assert run(api) == 0


def test_an_api_failure_fails_closed(capsys):
    api = FakeApi(mr(), GREEN, recorded_jobs(), fail_on="mr")
    assert run(api, {"AFAW_AUTO_MERGE": "true"}) == 2
    assert api.merged == []
    assert "503" in capsys.readouterr().err


def test_a_missing_default_branch_fails_closed(capsys):
    api = FakeApi(mr(), GREEN, recorded_jobs())
    assert merge_guard.run(api, 7, {"AFAW_BOT_USER_IDS": str(BOT)}) == 2


def test_a_bad_bot_id_list_fails_closed(capsys):
    api = FakeApi(mr(), GREEN, recorded_jobs())
    assert run(api, {"AFAW_BOT_USER_IDS": "12,abc"}) == 2


# ------------------------------------------------------------------ the HTTP edge


def test_the_merge_request_sends_the_sha_and_the_token_only_in_a_header():
    sent = {}

    def put(url, headers, body):
        sent.update(url=url, headers=headers, body=body)
        return {"state": "merged"}

    api = merge_guard.Api(
        "https://gitlab.com/api/v4", "88", "s3cret", get_json=lambda u: [], put=put
    )
    api.merge(7, "abc")
    assert sent["url"] == "https://gitlab.com/api/v4/projects/88/merge_requests/7/merge"
    assert sent["headers"]["PRIVATE-TOKEN"] == "s3cret"
    assert "s3cret" not in sent["url"] and "s3cret" not in json.dumps(sent["body"])
    # auto_merge: the guard runs inside the pipeline, so the merge waits for the checks to pass
    assert sent["body"] == {"sha": "abc", "auto_merge": True}


def test_merging_without_a_token_is_refused():
    api = merge_guard.Api("https://gitlab.com/api/v4", "88", None, get_json=lambda u: [])
    with pytest.raises(FactsError, match="AFAW_MERGE_TOKEN"):
        api.merge(7, "abc")


def test_main_fails_closed_outside_gitlab_ci(monkeypatch, capsys):
    for name in ("CI_API_V4_URL", "CI_PROJECT_ID", "CI_DEFAULT_BRANCH"):
        monkeypatch.delenv(name, raising=False)
    assert merge_guard.main(["--mr", "7"]) == 2
    assert "CI_API_V4_URL" in capsys.readouterr().err
