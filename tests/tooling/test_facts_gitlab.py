"""GitLab facts: pure parsers on recorded payloads of the public project, HTTP injected."""

import io
import json
import urllib.error
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from scripts.afaw_state.facts import (
    FactsError,
    Git,
    GitHub,
    GitLab,
    collect,
    forge_from_env,
    gitlab_ci_facts,
    http_get_json,
    mr_facts,
)
from tests.tooling.helpers import make_task

FIXTURES = Path(__file__).parent / "fixtures" / "gitlab"
MR6 = "feat/task-011-duo-agent-flow"
API = "https://gitlab.com/api/v4"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def pipeline(pid, sha, created, updated, status="success", source="push"):
    return {
        "id": pid,
        "sha": sha,
        "status": status,
        "source": source,
        "created_at": created,
        "updated_at": updated,
    }


def job(name, started="2026-10-24T10:00:00.000Z", duration=30.0, queued=1.0, status="success"):
    return {
        "name": name,
        "status": status,
        "started_at": started,
        "duration": duration,
        "queued_duration": queued,
    }


# ------------------------------------------------------------------ merge requests


def test_mr_facts_on_a_recorded_merged_merge_request():
    mr = next(m for m in load("merge_requests.json") if m["iid"] == 6)
    facts = mr_facts(mr, load("mr6_commits.json"))
    assert facts == {
        "pr_url": mr["web_url"],
        "pr_opened_at": "2026-10-24T23:40:52.389000Z",
        "merged_at": "2026-10-24T23:48:58.167000Z",
        "started_at": "2026-10-24T23:33:22Z",
        "last_commit_at": "2026-10-24T23:42:47Z",
    }


def test_mr_facts_of_an_open_merge_request_has_no_merge_time():
    mr = {"web_url": "u", "created_at": "2026-10-24T10:00:00.000Z", "merged_at": None}
    facts = mr_facts(mr, [])
    assert facts["merged_at"] is None and facts["started_at"] is None
    assert mr_facts(None, []) == {}


# ------------------------------------------------------------------ pipelines and jobs


def test_ci_facts_on_recorded_pipelines_and_jobs():
    pipelines = load("branch_pipelines.json")
    jobs = {2985416324: load("pipeline_2985416324_jobs.json")}
    facts = gitlab_ci_facts(pipelines, jobs)

    assert facts["ci_status"] == "success"
    assert facts["first_green_at"] == "2026-10-24T23:38:51.409000Z"
    assert facts["last_run_at"] == "2026-10-24T23:47:18.966000Z"
    ci = facts["ci"]
    assert (ci["runs"], ci["failed_runs"], ci["jobs"]) == (4, 0, 19)
    assert ci["pipelines"] == 4 and ci["retries"] == 0 and ci["missing_durations"] == 0
    assert ci["job_seconds"] == pytest.approx(
        sum(j["duration"] for j in jobs[2985416324]), abs=0.001
    )
    assert ci["job_minutes"] >= ci["job_seconds"] / 60  # per-job round up
    assert ci["queue_seconds"] == int(sum(j["queued_duration"] for j in jobs[2985416324]))


def test_no_pipelines_gives_no_ci_facts():
    assert gitlab_ci_facts([], {}) == {}


def test_first_green_needs_every_pipeline_of_a_commit_green():
    pipelines = [
        pipeline(1, "aaa", "2026-10-24T10:00:00Z", "2026-10-24T10:05:00Z", "failed"),
        pipeline(2, "aaa", "2026-10-24T10:00:00Z", "2026-10-24T10:06:00Z", source="web"),
        pipeline(3, "bbb", "2026-10-24T11:00:00Z", "2026-10-24T11:04:00Z"),
        pipeline(4, "bbb", "2026-10-24T11:00:00Z", "2026-10-24T11:09:00Z", source="web"),
    ]
    facts = gitlab_ci_facts(pipelines, {})
    assert facts["first_green_at"] == "2026-10-24T11:09:00Z"
    assert facts["ci_status"] == "success"
    assert facts["ci"]["failed_runs"] == 1


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("failed", "failure"),
        ("canceled", "failure"),
        ("running", "pending"),
        ("pending", "pending"),
    ],
)
def test_status_of_the_latest_commit(status, expected):
    green = pipeline(1, "aaa", "2026-10-24T10:00:00Z", "2026-10-24T10:05:00Z")
    latest = pipeline(2, "bbb", "2026-10-24T11:00:00Z", "2026-10-24T11:05:00Z", status)
    assert gitlab_ci_facts([green, latest], {})["ci_status"] == expected


def test_job_minutes_round_each_job_up_and_use_the_reported_duration():
    pipelines = [pipeline(1, "aaa", "2026-10-24T10:00:00Z", "2026-10-24T10:10:00Z")]
    jobs = {1: [job("a", duration=61.0), job("b", duration=0.2), job("c", duration=60.0)]}
    ci = gitlab_ci_facts(pipelines, jobs)["ci"]
    assert ci["job_seconds"] == pytest.approx(121.2)
    assert ci["job_minutes"] == 2 + 1 + 1
    assert ci["missing_durations"] == 0


def test_a_started_job_without_duration_is_missing_not_zero():
    pipelines = [pipeline(1, "aaa", "2026-10-24T10:00:00Z", "2026-10-24T10:10:00Z")]
    jobs = {1: [job("a", duration=61.0), job("b", duration=None)]}
    ci = gitlab_ci_facts(pipelines, jobs)["ci"]
    assert ci["job_minutes"] is None and ci["job_seconds"] is None
    assert ci["missing_durations"] == 1
    assert ci["jobs"] == 2


def test_a_job_that_never_started_is_not_a_missing_duration():
    pipelines = [pipeline(1, "aaa", "2026-10-24T10:00:00Z", "2026-10-24T10:10:00Z")]
    skipped = job("s", started=None, duration=None, queued=None, status="skipped")
    ci = gitlab_ci_facts(pipelines, {1: [job("a", duration=10.0), skipped]})["ci"]
    assert ci["missing_durations"] == 0 and ci["job_seconds"] == pytest.approx(10.0)
    assert ci["queue_seconds"] == 1


def test_retries_are_repeated_job_names_and_repeated_pipelines_of_one_commit():
    pipelines = [
        pipeline(1, "aaa", "2026-10-24T10:00:00Z", "2026-10-24T10:10:00Z", "failed"),
        pipeline(2, "aaa", "2026-10-24T10:20:00Z", "2026-10-24T10:30:00Z"),  # same sha, same source
        pipeline(
            3, "aaa", "2026-10-24T10:40:00Z", "2026-10-24T10:50:00Z", source="merge_request_event"
        ),
        pipeline(4, "bbb", "2026-10-24T11:00:00Z", "2026-10-24T11:10:00Z"),  # new commit: new work
    ]
    jobs = {
        1: [job("lint"), job("lint"), job("lint"), job("test")],  # lint ran 3 times: 2 retries
        2: [job("lint"), job("test")],
    }
    ci = gitlab_ci_facts(pipelines, jobs)["ci"]
    assert ci["pipelines"] == 4
    assert ci["retried_jobs"] == 2
    assert ci["pipeline_retries"] == 1
    assert ci["retries"] == 3


# ------------------------------------------------------------------ GitLab client


class Recorder:
    """Stands in for the HTTP layer: answers by URL fragment and records every URL."""

    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.urls: list[str] = []

    def __call__(self, url: str) -> Any:
        self.urls.append(url)
        for fragment, answer in self.answers.items():
            if fragment in url:
                return answer
        raise AssertionError(f"unexpected request: {url}")


def gitlab(answers: dict[str, Any]) -> tuple[GitLab, Recorder]:
    recorder = Recorder(answers)
    return GitLab(API, "88052530", None, get_json=recorder), recorder


def test_branch_facts_joins_the_merge_request_and_every_pipeline_of_the_branch():
    mrs = [m for m in load("merge_requests.json") if m["iid"] == 6]
    gl, rec = gitlab(
        {
            "/merge_requests?": mrs,
            "/merge_requests/6/commits": load("mr6_commits.json"),
            "/merge_requests/6/pipelines": load("mr6_pipelines.json"),
            "/pipelines?": load("branch_pipelines.json"),
            "/jobs": load("pipeline_2985416324_jobs.json"),
        }
    )
    pr_part, ci_part = gl.branch_facts(MR6)

    assert pr_part["merged_at"] == "2026-10-24T23:48:58.167000Z"
    assert ci_part["ci"]["pipelines"] == 4  # the union is deduplicated by pipeline id
    assert any("source_branch=feat%2Ftask-011-duo-agent-flow" in u for u in rec.urls)
    assert any("/pipelines?" in u and "ref=feat%2Ftask-011-duo-agent-flow" in u for u in rec.urls)
    assert any("/jobs?" in u and "include_retried=true" in u for u in rec.urls)
    assert all(u.startswith(f"{API}/projects/88052530/") for u in rec.urls)


def test_a_branch_without_merge_request_still_gets_its_pipelines():
    gl, _ = gitlab(
        {
            "/merge_requests?": [],
            "/pipelines?": [],
        }
    )
    assert gl.branch_facts("feat/none") == ({}, {})


def test_the_latest_merge_request_of_a_branch_wins():
    older = {**load("merge_requests.json")[0], "iid": 1, "created_at": "2026-10-01T00:00:00Z"}
    newer = {**older, "iid": 2, "created_at": "2026-10-02T00:00:00Z"}
    gl, rec = gitlab(
        {"/merge_requests?": [older, newer], "/merge_requests/2/": [], "/pipelines?": []}
    )
    gl.branch_facts("feat/x")
    assert any("/merge_requests/2/commits" in u for u in rec.urls)


def test_pagination_stops_at_a_short_page_and_fails_loudly_at_the_cap():
    full = [{"id": i} for i in range(100)]
    pages: list[int] = []

    def get(url: str) -> Any:
        pages.append(int(parse_qs(urlparse(url).query)["page"][0]))
        return full if pages[-1] < 3 else [{"id": 999}]

    gl = GitLab(API, "1", None, get_json=get)
    assert len(gl.pipelines_of_branch("b")) == 201
    assert pages == [1, 2, 3]

    gl = GitLab(API, "1", None, get_json=lambda url: full)
    with pytest.raises(FactsError, match="more than"):
        gl.pipelines_of_branch("b")


def test_a_token_is_sent_as_a_header_and_never_in_the_url():
    seen = {}

    def opener(req, timeout):
        seen["headers"] = dict(req.header_items())
        seen["url"] = req.full_url
        return io.BytesIO(b"[]")

    gl = GitLab(API, "1", "s3cret", opener=opener)
    gl.pipelines_of_branch("b")
    assert seen["headers"]["Private-token"] == "s3cret"
    assert "s3cret" not in seen["url"]


# ------------------------------------------------------------------ HTTP with retries


class Body(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("u", code, "msg", {}, io.BytesIO(b""))  # type: ignore[arg-type]


def test_retries_with_exponential_backoff_on_429_and_5xx():
    answers = [http_error(429), http_error(503), Body(b'{"ok": true}')]
    sleeps, timeouts = [], []

    def opener(req, timeout):
        timeouts.append(timeout)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    assert http_get_json("https://x/y", {}, opener=opener, sleep=sleeps.append) == {"ok": True}
    assert sleeps == [1, 2]
    assert timeouts == [30, 30, 30]


def test_does_not_retry_client_errors_and_gives_up_after_the_attempts():
    calls = []

    def not_found(req, timeout):
        calls.append(1)
        raise http_error(404)

    with pytest.raises(urllib.error.HTTPError):
        http_get_json("https://x/y", {}, opener=not_found, sleep=lambda s: None)
    assert len(calls) == 1

    calls.clear()

    def always_down(req, timeout):
        calls.append(1)
        raise http_error(500)

    with pytest.raises(FactsError, match="500"):
        http_get_json("https://x/y", {}, opener=always_down, sleep=lambda s: None, attempts=4)
    assert len(calls) == 4


def test_network_errors_are_retried_too():
    attempts = []

    def flaky(req, timeout):
        attempts.append(1)
        if len(attempts) < 2:
            raise urllib.error.URLError("reset")
        return Body(b"[]")

    assert http_get_json("https://x/y", {}, opener=flaky, sleep=lambda s: None) == []


# ------------------------------------------------------------------ choosing the forge


def test_the_forge_is_chosen_by_environment():
    gl = forge_from_env({"CI_API_V4_URL": API, "CI_PROJECT_ID": "7"})
    assert isinstance(gl, GitLab) and gl.project_id == "7"
    gh = forge_from_env({"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t"})
    assert isinstance(gh, GitHub) and gh.repo == "o/r"


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"CI_PROJECT_ID": "7"},
        {"CI_API_V4_URL": API},
        {"CI_API_V4_URL": API, "CI_PROJECT_ID": "7", "GITHUB_REPOSITORY": "o/r"},
    ],
)
def test_neither_or_both_forges_fail_loudly(env):
    with pytest.raises(FactsError):
        forge_from_env(env)


# ------------------------------------------------------------------ collect with a GitLab forge


class FakeGit(Git):
    def __init__(self) -> None:
        super().__init__(run=lambda args: "")

    def file_added_at(self, ref, path):
        return "2026-10-20T00:00:00Z"

    def branch_commit_at(self, branch):
        return None


def test_collect_works_with_gitlab_and_reuses_the_cache_of_merged_tasks():
    gl, rec = gitlab(
        {
            "/merge_requests?": [],
            "/pipelines?": [pipeline(5, "aaa", "2026-10-24T10:00:00Z", "2026-10-24T10:05:00Z")],
            "/jobs": [job("lint", duration=90.0)],
        }
    )
    tasks = [
        make_task("task_001", status="done", branch="feat/a"),
        make_task("task_002", status="in_progress", branch="feat/b"),
        make_task("task_003", status="backlog"),
    ]
    cache = {"task_001": {"merged_at": "2026-10-21T00:00:00Z", "ci": {"runs": 1}}}
    facts = collect(tasks, "gitlab/main", FakeGit(), gl, cache)

    assert facts["task_001"] == cache["task_001"]
    assert not any("feat%2Fa" in u for u in rec.urls)
    assert facts["task_002"]["ci"]["job_minutes"] == 2
    assert facts["task_002"]["ci_status"] == "success"
    assert facts["task_003"] == {"created_at": "2026-10-20T00:00:00Z"}
