#!/usr/bin/env python3
"""Ask the GitLab Duo Developer Flow to repair a failed pipeline, with no person in the middle.

Run by the ``request_fix`` job when a job of the pipeline failed and the hands-off switch is on:

* in a merge request pipeline it writes one note that mentions the flow's service account, with the
  failed jobs and the end of their logs; a mention starts a flow session (observed on 2026-10-25);
* in a pipeline of a branch with no merge request it opens one issue assigned to that account,
  labelled ``afaw-autoheal``, with the branch and the same facts; assigning an issue starts it.

Both are written with ``AFAW_MERGE_TOKEN``, which belongs to a person, because a bot or another flow
cannot start a flow. The same failing commit is never asked twice, and after CAP requests for one
merge request or branch the job says so and stops. Nothing here changes code, a branch or a merge
request: the flow does, and the pipeline gates judge what it writes.

Usage (in CI, from the environment): python -m scripts.request_fix
Exit codes: 0 done or nothing to do, 2 could not decide or write (fails closed).
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from scripts.afaw_state.facts import MAX_PAGES, PAGE_SIZE, FactsError
from scripts.merge_guard import CAP, GUARD_JOB

SELF_JOB = "request_fix"
FLOW_USERNAME = "duo-developer-gitlab-ai-hackathon"
LABEL = "afaw-autoheal"
GLOBAL_CAP = 6  # open autoheal issues of the whole project: a chain of new branches stops here
TAIL_LINES = 30
TAIL_CHARS = 1500
TIMEOUT = 30
_NOISE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|section_(?:start|end):\d+:\S*|\r")


def marker_for_sha(sha8: str) -> str:
    """The hidden comment that says this commit was already sent to the flow."""
    return f"<!-- afaw-autoheal sha={sha8} -->"


def marker_for_ref(ref: str) -> str:
    """The hidden comment that ties an issue to the branch it is about."""
    return f"<!-- afaw-autoheal ref={ref} -->"


def failing_jobs(jobs: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The jobs that failed and are allowed to block, without this guard's own jobs."""
    return [
        j
        for j in jobs
        if j["status"] == "failed"
        and not j.get("allow_failure")
        and j["name"] not in (GUARD_JOB, SELF_JOB)
    ]


def log_tail(trace: str) -> str:
    """The end of a job log without colour codes, section markers or blank lines."""
    lines = [line.rstrip() for line in _NOISE.sub("", trace).splitlines()]
    kept = "\n".join([line for line in lines if line.strip()][-TAIL_LINES:])
    return kept[-TAIL_CHARS:]


def _facts(api: Any, failed: Sequence[Mapping[str, Any]]) -> str:
    parts = []
    for j in failed:
        parts.append(f"- `{j['name']}` (stage {j.get('stage', '?')})")
    parts.append("")
    for j in failed:
        parts.append(
            f"End of the log of `{j['name']}`:\n```text\n{log_tail(api.job_trace(j['id']))}\n```"
        )
    return "\n".join(parts)


def _note(sha8: str, attempt: int, facts: str) -> str:
    return (
        f"@{FLOW_USERNAME} the pipeline of this merge request failed (commit {sha8}); this is "
        f"attempt {attempt} of {CAP}. Repair it on this branch and push the fix.\n\n"
        "Rules: change only what the failure needs; do not weaken, skip or delete a test; do not "
        "touch .gitlab-ci.yml, AGENTS.md, CODEOWNERS, state/config.json, "
        "state/equivalent_mutants.json or deploy/. A test that documents behaviour the code "
        'already has is declared with @pytest.mark.characterization(reason="...").\n\n'
        f"Failed jobs:\n{facts}\n\n{marker_for_sha(sha8)}"
    )


def _issue_text(ref: str, sha8: str, facts: str) -> str:
    return (
        f"A pipeline failed on branch `{ref}` at commit {sha8}. Repair it: fix the cause on a new "
        "branch and open a merge request into the default branch. Follow AGENTS.md: use the next "
        "free task id, do not weaken, skip or delete a test, and do not touch .gitlab-ci.yml, "
        "AGENTS.md, CODEOWNERS, state/config.json, state/equivalent_mutants.json or deploy/.\n\n"
        f"Failed jobs:\n{facts}\n\n{marker_for_ref(ref)}"
    )


class Api:
    """The GitLab endpoints the job reads and the two it writes."""

    def __init__(
        self,
        api_url: str,
        project_id: str,
        token: str | None,
        get_json: Callable[[str], Any] | None = None,
        get_text: Callable[[str], str] | None = None,
        post: Callable[[str, Mapping[str, str], Mapping[str, Any]], Any] | None = None,
    ) -> None:
        self._base = f"{api_url.rstrip('/')}"
        self._project = f"{self._base}/projects/{project_id}"
        self._token = token
        headers = {"PRIVATE-TOKEN": token} if token else {}
        self._get_json = get_json or (lambda url: _http_json(url, headers))
        self._get_text = get_text or (lambda url: _http_text(url, headers))
        self._post = post or _http_post

    def _pages(self, url: str) -> list[Any]:
        sep = "&" if "?" in url else "?"
        rows: list[Any] = []
        for page in range(1, MAX_PAGES + 1):
            chunk = self._get_json(f"{url}{sep}per_page={PAGE_SIZE}&page={page}")
            rows += chunk
            if len(chunk) < PAGE_SIZE:
                break
        return rows

    def pipeline_jobs(self, pipeline_id: int) -> list[Mapping[str, Any]]:
        return self._pages(f"{self._project}/pipelines/{pipeline_id}/jobs")

    def job_trace(self, job_id: int) -> str:
        return self._get_text(f"{self._project}/jobs/{job_id}/trace")

    def mr_notes(self, iid: int) -> list[Mapping[str, Any]]:
        return self._pages(f"{self._project}/merge_requests/{iid}/notes")

    def labeled_issues(self, label: str) -> list[Mapping[str, Any]]:
        return self._pages(
            f"{self._project}/issues?state=opened&labels={urllib.parse.quote(label)}"
        )

    def user_id(self, username: str) -> int:
        users = self._get_json(f"{self._base}/users?username={urllib.parse.quote(username)}")
        if not users:
            raise FactsError(f"no user named {username}")
        return int(users[0]["id"])

    def _write(self, path: str, body: Mapping[str, Any]) -> None:
        if not self._token:
            raise FactsError("AFAW_MERGE_TOKEN is not set; cannot ask the flow")
        headers = {"PRIVATE-TOKEN": self._token, "Content-Type": "application/json"}
        self._post(f"{self._project}/{path}", headers, body)

    def post_note(self, iid: int, body: str) -> None:
        self._write(f"merge_requests/{iid}/notes", {"body": body})

    def create_issue(self, title: str, description: str, assignee_id: int, label: str) -> None:
        self._write(
            "issues",
            {
                "title": title,
                "description": description,
                "assignee_ids": [assignee_id],
                "labels": label,
            },
        )


def _open(request: urllib.request.Request) -> bytes:
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
            data: bytes = response.read()
            return data
    except urllib.error.HTTPError as error:
        raise FactsError(f"GitLab refused the request: HTTP {error.code}") from None
    except urllib.error.URLError as error:
        raise FactsError(f"GitLab did not answer: {error.reason}") from None


def _http_json(url: str, headers: Mapping[str, str]) -> Any:
    return json.loads(_open(urllib.request.Request(url, headers=dict(headers))))


def _http_text(url: str, headers: Mapping[str, str]) -> str:
    return _open(urllib.request.Request(url, headers=dict(headers))).decode("utf-8", "replace")


def _http_post(url: str, headers: Mapping[str, str], body: Mapping[str, Any]) -> Any:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=dict(headers), method="POST"
    )
    return json.loads(_open(request) or b"{}")


def _ask_in_merge_request(api: Any, iid: int, sha8: str, facts: str) -> None:
    marks = [n["body"] for n in api.mr_notes(iid) if "<!-- afaw-autoheal sha=" in n.get("body", "")]
    if any(marker_for_sha(sha8) in body for body in marks):
        print(f"commit {sha8} was already sent to the flow; nothing to do")
    elif len(marks) >= CAP:
        print(f"{len(marks)} requests were already made for !{iid}: the cap of {CAP} is reached")
    else:
        api.post_note(iid, _note(sha8, len(marks) + 1, facts))
        print(f"asked @{FLOW_USERNAME} on !{iid} (attempt {len(marks) + 1} of {CAP})")


def _ask_with_an_issue(api: Any, ref: str, sha8: str, names: str, facts: str) -> None:
    title = f"autoheal: {names} @ {sha8}"
    issues = api.labeled_issues(LABEL)
    sent = [i for i in issues if marker_for_ref(ref) in i.get("description", "")]
    if any(i["title"] == title for i in issues):
        print(f"an open issue already covers {title!r}; nothing to do")
    elif len(issues) >= GLOBAL_CAP:
        print(f"{len(issues)} open autoheal issues: cap of {GLOBAL_CAP} reached")
    elif len(sent) >= CAP:
        print(f"{len(sent)} issues were already opened for {ref}: the cap of {CAP} is reached")
    else:
        api.create_issue(title, _issue_text(ref, sha8, facts), api.user_id(FLOW_USERNAME), LABEL)
        print(f"opened {title!r} for {FLOW_USERNAME}")


def run(api: Any, env: Mapping[str, str]) -> int:
    """Ask the flow to repair the failed jobs of the current pipeline, once per commit."""
    try:
        pipeline_id = int(env["CI_PIPELINE_ID"])
        sha8 = env["CI_COMMIT_SHA"][:8]
        failed = failing_jobs(api.pipeline_jobs(pipeline_id))
        if not failed:
            print("no failed job; nothing to ask")
            return 0
        facts = _facts(api, failed)
        iid = env.get("CI_MERGE_REQUEST_IID")
        if iid:
            _ask_in_merge_request(api, int(iid), sha8, facts)
        else:
            names = ", ".join(j["name"] for j in failed)
            _ask_with_an_issue(api, env["CI_COMMIT_REF_NAME"], sha8, names, facts)
    except (FactsError, KeyError, ValueError) as error:
        print(f"request_fix: could not ask the flow: {error}", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    missing = [n for n in ("CI_API_V4_URL", "CI_PROJECT_ID") if not os.environ.get(n)]
    if missing:
        print(f"request_fix: {', '.join(missing)} not set", file=sys.stderr)
        return 2
    api = Api(
        os.environ["CI_API_V4_URL"], os.environ["CI_PROJECT_ID"], os.environ.get("AFAW_MERGE_TOKEN")
    )
    return run(api, os.environ)


if __name__ == "__main__":
    raise SystemExit(main())
