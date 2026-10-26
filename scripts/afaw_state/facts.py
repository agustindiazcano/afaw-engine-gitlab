"""Measured facts per task, taken from git and from the GitLab or GitHub REST API.

Nothing here is declared by an agent. The parsing functions are pure and are
tested on recorded API payloads; the I/O is at the edges (``Git``, ``GitHub``,
``GitLab``). The forge is chosen by environment (``forge_from_env``), never guessed.
"""

from __future__ import annotations

import http.client
import json
import math
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from .derive import parse_ts, require_ts

GREEN_CONCLUSIONS = frozenset({"success", "skipped", "neutral"})
FAILED_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure"})
GITLAB_GREEN = frozenset({"success"})
GITLAB_FAILED = frozenset({"failed", "canceled"})
MAX_PAGES = 10
PAGE_SIZE = 100


class FactsError(RuntimeError):
    """A fact could not be measured; the collector stops instead of storing a guess."""


def _iso(ts: datetime | None) -> str | None:
    return ts.isoformat().replace("+00:00", "Z") if ts else None


def _utc_iso(ts: str | None) -> str | None:
    return _iso(require_ts(ts).astimezone(UTC)) if ts else None


def _latest(values: Iterable[str | None]) -> str | None:
    parsed = [require_ts(v) for v in values if v]
    return _iso(max(parsed)) if parsed else None


def pr_facts(pr: Mapping[str, Any] | None, commits: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Facts from one pull request and its commits."""
    if pr is None:
        return {}
    dates = [require_ts(c["commit"]["committer"]["date"]) for c in commits]
    return {
        "pr_url": pr["html_url"],
        "pr_opened_at": _iso(require_ts(pr["created_at"])),
        "merged_at": _iso(parse_ts(pr.get("merged_at"))),
        "started_at": _iso(min(dates)) if dates else None,
        "last_commit_at": _iso(max(dates)) if dates else None,
    }


def ci_facts(
    runs: list[Mapping[str, Any]], jobs_by_run: Mapping[int, list[Mapping[str, Any]]]
) -> dict[str, Any]:
    """Facts from the workflow runs of one branch and their jobs.

    first_green_at: the earliest time at which every run of one commit had
                    finished green (success, skipped or neutral).
    ci_status:      the state of the runs of the latest commit.
    ci.queue_seconds: sum over jobs of (started_at - created_at).
    ci.job_minutes:   sum over jobs of their duration rounded up to a whole
                      minute, the unit GitHub uses to bill standard runners.
                      Runner price multipliers are not applied; the billing
                      report remains the ground truth for cost.
    """
    if not runs:
        return {}

    by_sha: dict[str, list[Mapping[str, Any]]] = {}
    for run in runs:
        by_sha.setdefault(run["head_sha"], []).append(run)

    green_times = []
    for sha_runs in by_sha.values():
        if all(
            r["status"] == "completed" and r["conclusion"] in GREEN_CONCLUSIONS for r in sha_runs
        ):
            green_times.append(max(require_ts(r["updated_at"]) for r in sha_runs))

    latest_sha = max(by_sha, key=lambda s: max(require_ts(r["created_at"]) for r in by_sha[s]))
    latest = by_sha[latest_sha]
    if any(r.get("conclusion") in FAILED_CONCLUSIONS for r in latest):
        status = "failure"
    elif all(r["status"] == "completed" and r["conclusion"] in GREEN_CONCLUSIONS for r in latest):
        status = "success"
    else:
        status = "pending"

    jobs = [j for r in runs for j in jobs_by_run.get(r["id"], [])]
    queue = 0
    minutes = 0
    for job in jobs:
        created, started, completed = (
            parse_ts(job.get(k)) for k in ("created_at", "started_at", "completed_at")
        )
        if created and started:
            queue += max(0, int((started - created).total_seconds()))
        if started and completed:
            minutes += math.ceil(max(0.0, (completed - started).total_seconds()) / 60)

    return {
        "first_green_at": _iso(min(green_times)) if green_times else None,
        "ci_status": status,
        "last_run_at": _latest(r["updated_at"] for r in runs),
        "ci": {
            "runs": len(runs),
            "failed_runs": sum(1 for r in runs if r.get("conclusion") in FAILED_CONCLUSIONS),
            "jobs": len(jobs),
            "queue_seconds": queue,
            "job_minutes": minutes,
        },
    }


def mr_facts(mr: Mapping[str, Any] | None, commits: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Facts from one GitLab merge request and its commits (same fields as ``pr_facts``)."""
    if mr is None:
        return {}
    dates = [require_ts(c["committed_date"]).astimezone(UTC) for c in commits]
    return {
        "pr_url": mr["web_url"],
        "pr_opened_at": _utc_iso(mr["created_at"]),
        "merged_at": _utc_iso(mr.get("merged_at")),
        "started_at": _iso(min(dates)) if dates else None,
        "last_commit_at": _iso(max(dates)) if dates else None,
    }


def gitlab_ci_facts(
    pipelines: list[Mapping[str, Any]], jobs_by_pipeline: Mapping[int, list[Mapping[str, Any]]]
) -> dict[str, Any]:
    """Facts from the pipelines of one merge request or branch and their jobs.

    first_green_at: the earliest time at which every pipeline of one commit was green.
    ci_status:      the state of the pipelines of the latest commit; a canceled one counts as
                    failure because nothing is running and it is not green.
    ci.queue_seconds: sum of the ``queued_duration`` GitLab reports, truncated to seconds.
    ci.job_seconds:   sum of the ``duration`` GitLab reports for jobs that started.
    ci.job_minutes:   the same durations with each job rounded up to a whole minute, the unit
                      of ``ci.job_minutes`` on GitHub. Billing is not claimed to be equal.
    ci.missing_durations: jobs that started but report no duration. When there is one,
                      job_seconds and job_minutes are null (never zero or a partial sum).
    ci.pipelines:     every pipeline listed for the merge request or branch.
    ci.retried_jobs:  jobs that ran again with the same name in the same pipeline.
    ci.pipeline_retries: pipelines beyond the first for the same commit and the same source
                      (a new commit is new work, not a retry).
    ci.retries:       retried_jobs + pipeline_retries.
    """
    if not pipelines:
        return {}

    by_sha: dict[str, list[Mapping[str, Any]]] = {}
    for pipeline in pipelines:
        by_sha.setdefault(pipeline["sha"], []).append(pipeline)

    green_times = [
        max(require_ts(p["updated_at"]) for p in group)
        for group in by_sha.values()
        if all(p["status"] in GITLAB_GREEN for p in group)
    ]
    latest = by_sha[max(by_sha, key=lambda s: max(require_ts(p["created_at"]) for p in by_sha[s]))]
    if any(p["status"] in GITLAB_FAILED for p in latest):
        status = "failure"
    elif all(p["status"] in GITLAB_GREEN for p in latest):
        status = "success"
    else:
        status = "pending"

    jobs = [j for p in pipelines for j in jobs_by_pipeline.get(p["id"], [])]
    queue = sum(j["queued_duration"] for j in jobs if j.get("queued_duration") is not None)
    started = [j for j in jobs if j.get("started_at")]
    durations = [j.get("duration") for j in started]
    missing = sum(1 for d in durations if d is None)
    known = [max(0.0, float(d)) for d in durations if d is not None]
    retried_jobs = sum(
        count - 1
        for p in pipelines
        for count in Counter(j["name"] for j in jobs_by_pipeline.get(p["id"], [])).values()
    )
    pipeline_retries = len(pipelines) - len({(p["sha"], p.get("source")) for p in pipelines})

    return {
        "first_green_at": _iso(min(green_times).astimezone(UTC)) if green_times else None,
        "ci_status": status,
        "last_run_at": _latest(p["updated_at"] for p in pipelines),
        "ci": {
            "runs": len(pipelines),
            "failed_runs": sum(1 for p in pipelines if p["status"] in GITLAB_FAILED),
            "jobs": len(jobs),
            "queue_seconds": int(queue),
            "job_seconds": None if missing else round(sum(known), 3),
            "job_minutes": None if missing else sum(math.ceil(d / 60) for d in known),
            "missing_durations": missing,
            "pipelines": len(pipelines),
            "retried_jobs": retried_jobs,
            "pipeline_retries": pipeline_retries,
            "retries": retried_jobs + pipeline_retries,
        },
    }


def combine(
    created_at: str | None,
    branch_commit_at: str | None,
    pr: Mapping[str, Any],
    ci: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge the facts of one task into the shape that ``derive`` reads."""
    facts: dict[str, Any] = {"created_at": created_at}
    facts.update({k: v for k, v in pr.items() if k != "last_commit_at"})
    facts.update({k: v for k, v in ci.items() if k != "last_run_at"})
    facts["last_activity_at"] = _latest(
        [branch_commit_at, pr.get("last_commit_at"), ci.get("last_run_at")]
    )
    return facts


# ---------------------------------------------------------------- I/O edges


class Git:
    def __init__(self, run: Callable[[list[str]], str] | None = None) -> None:
        self._run = run or (
            lambda args: (
                subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout
            )
        )

    def file_added_at(self, ref: str, path: str) -> str | None:
        out = self._run(["log", "--diff-filter=A", "--format=%cI", ref, "--", path]).split()
        return _iso(require_ts(out[-1])) if out else None

    def branch_commit_at(self, branch: str) -> str | None:
        try:
            out = self._run(["log", "-1", "--format=%cI", f"origin/{branch}"]).strip()
        except subprocess.CalledProcessError:
            return None  # branch deleted after merge; the PR commits cover it
        return _iso(require_ts(out)) if out else None


class GitHub:
    API = "https://api.github.com"

    def __init__(
        self, repo: str, token: str | None, get_json: Callable[[str], Any] | None = None
    ) -> None:
        self.repo = repo
        self.owner = repo.split("/")[0]
        self._token = token
        self._get_json = get_json or self._http_get

    def _http_get(self, url: str) -> Any:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        if self._token:
            req.add_header("Authorization", f"Bearer {self._token}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)

    def _url(self, path: str, **params: Any) -> str:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        return f"{self.API}/repos/{self.repo}/{path}" + (f"?{query}" if query else "")

    def _pages(self, path: str, key: str | None, max_pages: int, **params: Any) -> list[Any]:
        items: list[Any] = []
        for page in range(1, max_pages + 1):
            data = self._get_json(self._url(path, per_page=100, page=page, **params))
            batch = data[key] if key else data
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    def pull_request(self, branch: str) -> Mapping[str, Any] | None:
        pulls = self._get_json(
            self._url("pulls", head=f"{self.owner}:{branch}", state="all", per_page=100)
        )
        if not pulls:
            return None
        latest: Mapping[str, Any] = max(pulls, key=lambda p: require_ts(p["created_at"]))
        return latest

    def pr_commits(self, number: int) -> list[Mapping[str, Any]]:
        return self._pages(f"pulls/{number}/commits", None, 3)

    def runs(self, branch: str) -> list[Mapping[str, Any]]:
        return self._pages("actions/runs", "workflow_runs", 10, branch=branch)

    def jobs(self, run_id: int) -> list[Mapping[str, Any]]:
        return self._pages(f"actions/runs/{run_id}/jobs", "jobs", 5, filter="all")

    def branch_facts(self, branch: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Pull request facts and CI facts of one branch."""
        pr = self.pull_request(branch)
        pr_part = pr_facts(pr, self.pr_commits(pr["number"]) if pr else [])
        runs = self.runs(branch)
        return pr_part, ci_facts(runs, {r["id"]: self.jobs(r["id"]) for r in runs})


def http_get_json(
    url: str,
    headers: Mapping[str, str],
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
    attempts: int = 4,
    timeout: float = 30,
) -> Any:
    """GET a JSON document with a timeout; 429, 5xx, network errors and responses cut in the
    middle are retried with exponential backoff (1 s, 2 s, 4 s, ...). Other HTTP errors are
    raised as they are."""
    last = "no attempt"
    for attempt in range(attempts):
        if attempt:
            sleep(2 ** (attempt - 1))
        try:
            with opener(urllib.request.Request(url, headers=dict(headers)), timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise
            last = f"HTTP {error.code}"
        except (urllib.error.URLError, TimeoutError, http.client.HTTPException) as error:
            last = f"network error: {error!r}"
    raise FactsError(f"GET {url.split('?')[0]} failed after {attempts} attempts ({last})")


class GitLab:
    """Reads merge requests, pipelines and jobs of one project from the REST API v4.

    This project is public, so reads need no token (CI_JOB_TOKEN is documented only for a few
    endpoints, none of them the pipeline ones). ``token`` is optional, for a private project, and
    is sent as a header, never in a URL.
    """

    def __init__(
        self,
        api_url: str,
        project_id: str,
        token: str | None,
        get_json: Callable[[str], Any] | None = None,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.project_id = project_id
        self._headers = {"PRIVATE-TOKEN": token} if token else {}
        self._opener = opener
        self._get_json = get_json or self._http_get

    def _http_get(self, url: str) -> Any:
        return http_get_json(url, self._headers, opener=self._opener)

    def _url(self, path: str, **params: Any) -> str:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        return f"{self.api_url}/projects/{self.project_id}/{path}" + (f"?{query}" if query else "")

    def _pages(self, path: str, **params: Any) -> list[Any]:
        items: list[Any] = []
        for page in range(1, MAX_PAGES + 1):
            batch = self._get_json(self._url(path, per_page=PAGE_SIZE, page=page, **params))
            items.extend(batch)
            if len(batch) < PAGE_SIZE:
                return items
        raise FactsError(f"{path}: more than {MAX_PAGES} pages; refusing to use a partial list")

    def merge_request(self, branch: str) -> Mapping[str, Any] | None:
        mrs = self._pages("merge_requests", source_branch=branch, state="all")
        if not mrs:
            return None
        latest: Mapping[str, Any] = max(mrs, key=lambda m: require_ts(m["created_at"]))
        return latest

    def mr_commits(self, iid: int) -> list[Mapping[str, Any]]:
        return self._pages(f"merge_requests/{iid}/commits")

    def mr_pipelines(self, iid: int) -> list[Mapping[str, Any]]:
        return self._pages(f"merge_requests/{iid}/pipelines")

    def pipeline(self, pipeline_id: int) -> Mapping[str, Any]:
        pipeline: Mapping[str, Any] = self._get_json(self._url(f"pipelines/{pipeline_id}"))
        return pipeline

    def pipelines_of_branch(self, branch: str) -> list[Mapping[str, Any]]:
        return self._pages("pipelines", ref=branch)

    def jobs(self, pipeline_id: int) -> list[Mapping[str, Any]]:
        return self._pages(f"pipelines/{pipeline_id}/jobs", include_retried="true")

    def branch_facts(self, branch: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Merge request facts and CI facts of one branch.

        The pipelines are the union, by id, of the merge request pipelines and the pipelines
        of the branch, so those run before the merge request was opened are counted too.
        """
        mr = self.merge_request(branch)
        mr_part = mr_facts(mr, self.mr_commits(mr["iid"]) if mr else [])
        pipelines = {p["id"]: p for p in self.pipelines_of_branch(branch)}
        if mr:
            pipelines.update({p["id"]: p for p in self.mr_pipelines(mr["iid"])})
        listed = list(pipelines.values())
        return mr_part, gitlab_ci_facts(listed, {p["id"]: self.jobs(p["id"]) for p in listed})


Forge = GitHub | GitLab


def forge_from_env(env: Mapping[str, str]) -> Forge:
    """GitLab when CI_API_V4_URL and CI_PROJECT_ID are set, GitHub when GITHUB_REPOSITORY is.

    Neither, only half of the GitLab pair, or both forges raise ``FactsError``: never a guess.
    """
    api_url, project_id = env.get("CI_API_V4_URL"), env.get("CI_PROJECT_ID")
    repo = env.get("GITHUB_REPOSITORY")
    if bool(api_url) != bool(project_id):
        raise FactsError("CI_API_V4_URL and CI_PROJECT_ID must be set together")
    if api_url and project_id and repo:
        raise FactsError("both GitLab (CI_API_V4_URL) and GitHub (GITHUB_REPOSITORY) are set")
    if api_url and project_id:
        return GitLab(api_url, project_id, env.get("GITLAB_TOKEN") or None)
    if repo:
        return GitHub(repo, env.get("GITHUB_TOKEN"))
    raise FactsError(
        "no forge configured: set CI_API_V4_URL and CI_PROJECT_ID (GitLab) "
        "or GITHUB_REPOSITORY (GitHub)"
    )


def collect(
    tasks: list[Mapping[str, Any]],
    ref: str,
    git: Git,
    forge: Forge,
    cache: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Facts for every task that has a branch. Facts of merged tasks are final and reused
    from the cache."""
    cache = cache or {}
    facts: dict[str, dict[str, Any]] = {}
    for task in tasks:
        task_id = task["id"]
        cached = cache.get(task_id)
        if cached and cached.get("merged_at"):
            facts[task_id] = dict(cached)
            continue
        created = git.file_added_at(ref, f"state/tasks/{task_id}.json")
        branch = task.get("branch")
        if not branch:
            facts[task_id] = {"created_at": created}
            continue
        pr_part, ci_part = forge.branch_facts(branch)
        facts[task_id] = combine(created, git.branch_commit_at(branch), pr_part, ci_part)
    return facts
