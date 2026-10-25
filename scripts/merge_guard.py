#!/usr/bin/env python3
"""Deterministic merge guard: the cap of automatic fix attempts and the rule for an automatic merge.

Reads one merge request, its latest pipeline and that pipeline's jobs from the GitLab REST API v4
and decides, with no model involved:

* fix attempts: a commit pushed by a Duo flow service account (ids in AFAW_BOT_USER_IDS) after
  the first failed pipeline of the merge request. GitLab documents no cap, so it is counted here.
  More than CAP attempts fail this job (exit 1), which blocks the merge.
* who made the change: the merge request author is the person who triggered a flow (composite
  identity), so it decides nothing. The head pipeline must have been started by a service account
  in AFAW_BOT_USER_IDS and every commit must be authored by a service account address. With no id
  configured nothing is merged automatically.
* merge: yes only when the merge request is open, not a draft, targets the default branch, has
  no conflicts and no unresolved blocking discussion; its latest pipeline is for the head
  commit; every other job of that pipeline has the status success; and red_check, mutation_gate
  and security_gate are among them.

The merge itself happens only when AFAW_AUTO_MERGE is exactly "true" and AFAW_MERGE_TOKEN is set
(a project access token that is allowed to merge). Without them the verdict is only printed.

Run in CI (merge request pipelines): python -m scripts.merge_guard --mr "$CI_MERGE_REQUEST_IID"
Exit codes: 0 verdict printed, 1 the cap of fix attempts was exceeded, 2 could not decide
(fails closed: nothing is merged).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from scripts.afaw_state.derive import require_ts
from scripts.afaw_state.facts import MAX_PAGES, PAGE_SIZE, FactsError, http_get_json
from scripts.service_accounts import is_service_account_email

CAP = 3
REQUIRED_JOBS = ("red_check", "mutation_gate", "security_gate")
GUARD_JOB = "merge_guard"
DRAFT_REASON = "merge request is a draft"
_DRAFT_MARKER = re.compile(r"^\s*(?:draft:|\[draft\]|\(draft\))\s*", re.IGNORECASE)
TIMEOUT = 30


@dataclass(frozen=True)
class Verdict:
    """Whether the merge request may be merged, and every reason it may not."""

    merge: bool
    reasons: list[str]


def fix_attempts(pipelines: list[Mapping[str, Any]], bot_ids: set[int]) -> int:
    """Distinct commits pushed by a bot after the first failed pipeline of the merge request."""
    failed = [require_ts(p["created_at"]) for p in pipelines if p["status"] == "failed"]
    if not failed:
        return 0
    first_failure = min(failed)
    return len(
        {
            p["sha"]
            for p in pipelines
            if (p.get("user") or {}).get("id") in bot_ids
            and require_ts(p["created_at"]) > first_failure
        }
    )


def identity_reasons(
    pipeline: Mapping[str, Any], bot_ids: frozenset[int], commit_emails: Sequence[str]
) -> list[str]:
    """Why the change is not the work of a service account (empty when it is)."""
    if not bot_ids:
        return ["AFAW_BOT_USER_IDS is empty: a service account cannot be told from a person"]
    reasons: list[str] = []
    pusher = pipeline.get("user") or {}
    if pusher.get("id") not in bot_ids:
        who = pusher.get("username") or "an unknown user"
        reasons.append(f"the head pipeline was started by {who}, not by a service account")
    if not commit_emails:
        reasons.append("no commit found for the merge request")
    reasons += [
        f"a commit is authored by {email}, not by a service account"
        for email in sorted({e for e in commit_emails if not is_service_account_email(e)})
    ]
    return reasons


def ready_title(title: str) -> str:
    """``title`` without a leading Draft marker; GitLab derives the draft state from it."""
    return _DRAFT_MARKER.sub("", title, count=1)


def merge_verdict(
    mr: Mapping[str, Any],
    pipeline: Mapping[str, Any] | None,
    jobs: list[Mapping[str, Any]],
    attempts: int,
    default_branch: str,
    bot_ids: frozenset[int] | None = None,
    commit_emails: Sequence[str] = (),
) -> Verdict:
    """The merge rule; ``jobs`` are the jobs of ``pipeline`` (this guard job is ignored).

    With ``bot_ids`` the change must also be the work of a service account.
    """
    reasons: list[str] = []
    if mr["state"] != "opened":
        reasons.append("merge request is not open")
    if mr["draft"]:
        reasons.append(DRAFT_REASON)
    if mr["target_branch"] != default_branch:
        reasons.append(f"target branch is {mr['target_branch']}, not {default_branch}")
    if mr["has_conflicts"]:
        reasons.append("merge request has conflicts")
    if not mr["blocking_discussions_resolved"]:
        reasons.append("blocking discussions are not resolved")
    if pipeline is None:
        reasons.append("no pipeline for the merge request")
    else:
        if pipeline["sha"] != mr["sha"]:
            reasons.append("the latest pipeline is not for the head commit")
        others = [j for j in jobs if j["name"] != GUARD_JOB]
        reasons += [f"{j['name']} is {j['status']}" for j in others if j["status"] != "success"]
        present = {j["name"] for j in others}
        reasons += [
            f"required job {name} is missing" for name in REQUIRED_JOBS if name not in present
        ]
        if bot_ids is not None:
            reasons += identity_reasons(pipeline, bot_ids, commit_emails)
    if attempts > CAP:
        reasons.append(f"{attempts} automatic fix attempts exceed the cap of {CAP}")
    return Verdict(not reasons, reasons)


class Api:
    """The few GitLab endpoints the guard reads, and the one it may write (the merge)."""

    def __init__(
        self,
        api_url: str,
        project_id: str,
        token: str | None,
        get_json: Callable[[str], Any] | None = None,
        put: Callable[[str, Mapping[str, str], Mapping[str, Any]], Any] | None = None,
    ) -> None:
        self._base = f"{api_url.rstrip('/')}/projects/{project_id}"
        self._token = token
        self._get_json = get_json or (lambda url: http_get_json(url, {}))
        self._put = put or _http_put

    def _pages(self, path: str) -> list[Any]:
        items: list[Any] = []
        for page in range(1, MAX_PAGES + 1):
            query = urllib.parse.urlencode({"per_page": PAGE_SIZE, "page": page})
            batch = self._get_json(f"{self._base}/{path}?{query}")
            items.extend(batch)
            if len(batch) < PAGE_SIZE:
                return items
        raise FactsError(f"{path}: more than {MAX_PAGES} pages; refusing to use a partial list")

    def get_mr(self, iid: int) -> Mapping[str, Any]:
        mr: Mapping[str, Any] = self._get_json(f"{self._base}/merge_requests/{iid}")
        return mr

    def mr_pipelines(self, iid: int) -> list[Mapping[str, Any]]:
        return self._pages(f"merge_requests/{iid}/pipelines")

    def mr_commits(self, iid: int) -> list[Mapping[str, Any]]:
        return self._pages(f"merge_requests/{iid}/commits")

    def pipeline(self, pipeline_id: int) -> Mapping[str, Any]:
        """One pipeline in full: the list does not carry the user who pushed."""
        pipeline: Mapping[str, Any] = self._get_json(f"{self._base}/pipelines/{pipeline_id}")
        return pipeline

    def pipeline_jobs(self, pipeline_id: int) -> list[Mapping[str, Any]]:
        return self._pages(f"pipelines/{pipeline_id}/jobs")

    def merge(self, iid: int, sha: str) -> None:
        """Merge once the checks pass, and only if the head of the merge request is still ``sha``.

        The guard runs inside the pipeline, so ``auto_merge`` (documented on the merge request
        API page) makes GitLab wait for the pipeline to finish instead of failing now.
        """
        if not self._token:
            raise FactsError("AFAW_MERGE_TOKEN is not set; cannot merge")
        self._put(
            f"{self._base}/merge_requests/{iid}/merge",
            {"PRIVATE-TOKEN": self._token, "Content-Type": "application/json"},
            {"sha": sha, "auto_merge": True},
        )


    def mark_ready(self, iid: int, title: str) -> None:
        """Take the merge request out of Draft by writing ``title`` without its Draft marker."""
        if not self._token:
            raise FactsError("AFAW_MERGE_TOKEN is not set; cannot mark the merge request ready")
        self._put(
            f"{self._base}/merge_requests/{iid}",
            {"PRIVATE-TOKEN": self._token, "Content-Type": "application/json"},
            {"title": title},
        )


def _http_put(url: str, headers: Mapping[str, str], body: Mapping[str, Any]) -> Any:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=dict(headers), method="PUT"
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise FactsError(f"the merge was refused: HTTP {error.code}") from None


def _bot_ids(raw: str) -> set[int]:
    return {int(part) for part in raw.split(",") if part.strip()}


def run(api: Api, iid: int, env: Mapping[str, str]) -> int:
    """Decide for merge request ``iid``; merge it if the rule and the switch allow it."""
    default_branch = env.get("CI_DEFAULT_BRANCH")
    if not default_branch:
        print("merge_guard: CI_DEFAULT_BRANCH is not set", file=sys.stderr)
        return 2
    try:
        bot_ids = _bot_ids(env.get("AFAW_BOT_USER_IDS", ""))
        mr = api.get_mr(iid)
        pipelines = [api.pipeline(p["id"]) for p in api.mr_pipelines(iid)]
        head = max(pipelines, key=lambda p: require_ts(p["created_at"]), default=None)
        jobs = api.pipeline_jobs(head["id"]) if head else []
        attempts = fix_attempts(pipelines, bot_ids)
        emails = [c.get("author_email", "") for c in api.mr_commits(iid)]
        verdict = merge_verdict(
            mr, head, jobs, attempts, default_branch, frozenset(bot_ids), emails
        )
        if (
            env.get("AFAW_AUTO_MERGE") == "true"
            and verdict.reasons == [DRAFT_REASON]
            and attempts <= CAP
        ):
            # Only the draft state holds it back and a service account made every change: the
            # gates have judged it, so the engine takes it out of Draft, not a person.
            api.mark_ready(iid, ready_title(mr["title"]))
            print(f"!{iid} was a draft and every other rule holds: made ready")
            verdict = Verdict(True, [])
        print(f"merge: {'yes' if verdict.merge else 'no'}")
        for reason in verdict.reasons:
            print(f"  - {reason}")
        print(f"automatic fix attempts: {attempts} (cap {CAP})")
        if attempts > CAP:
            return 1
        if verdict.merge:
            if env.get("AFAW_AUTO_MERGE") == "true":
                api.merge(iid, mr["sha"])
                print(f"!{iid} set to merge at {mr['sha']} when the pipeline passes")
            else:
                print("not merged: set AFAW_AUTO_MERGE=true to merge automatically")
    except (FactsError, urllib.error.URLError, KeyError, ValueError) as error:
        print(f"merge_guard: could not decide: {error}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mr", type=int, required=True, help="merge request iid")
    args = parser.parse_args(argv)
    missing = [n for n in ("CI_API_V4_URL", "CI_PROJECT_ID") if not os.environ.get(n)]
    if missing:
        print(f"merge_guard: {', '.join(missing)} not set", file=sys.stderr)
        return 2
    api = Api(
        os.environ["CI_API_V4_URL"], os.environ["CI_PROJECT_ID"], os.environ.get("AFAW_MERGE_TOKEN")
    )
    return run(api, args.mr, os.environ)


if __name__ == "__main__":
    raise SystemExit(main())
