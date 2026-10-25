#!/usr/bin/env python3
"""DEMO ON and DEMO OFF: start and stop the hands-off demonstration.

``on`` turns the hands-off switch on (the CI/CD variable ``AFAW_AUTO_MERGE`` set to ``true``),
checks that the variables the loop needs exist, and opens the demo issues assigned to the GitLab Duo
Developer Flow. From there the loop runs by itself: the flow opens a merge request, the pipeline
gates judge it, ``merge_guard`` takes it out of Draft and merges it, ``main`` releases and deploys.
A failed pipeline is handed back to the flow by ``request_fix``.

``off`` sets ``AFAW_AUTO_MERGE`` to ``false`` and closes the open demo and autoheal issues, so
nothing else merges or is asked of the flow. It does not delete branches or close merge requests.

The token is read from the environment (``GITLAB_TOKEN``, scope ``api``) and is never printed.

Usage:
    GITLAB_TOKEN=... python -m scripts.demo on [--issues 1]
    GITLAB_TOKEN=... python -m scripts.demo off
Exit codes: 0 done, 2 could not do it (fails closed).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any

from scripts.afaw_state.facts import MAX_PAGES, PAGE_SIZE, FactsError

API_URL = "https://gitlab.com/api/v4"
PROJECT = "gitlab-ai-hackathon%2Ftranscend-october-2026%2F43344247%2Fshowcase"
FLOW_USERNAME = "duo-developer-gitlab-ai-hackathon"
SWITCH = "AFAW_AUTO_MERGE"
REQUIRED = ("AFAW_BOT_USER_IDS", "AFAW_MERGE_TOKEN")
DEMO_LABEL = "demo"
CLOSE_LABELS = (DEMO_LABEL, "afaw-autoheal")
TIMEOUT = 30


def _issue_text(file_name: str, task_id: str) -> str:
    return (
        "Demo of the hands-off loop. Keep the change tiny and follow AGENTS.md.\n\n"
        f"Create one new file, docs/submission/{file_name}.md, with a first-level heading "
        '"Hands-off demo" and one paragraph in English saying that this file was written by the '
        "GitLab Duo Developer Flow from this issue, that merge_guard is expected to merge it with "
        "no person, and that nothing in the application depends on it.\n\n"
        "Rules from AGENTS.md that apply:\n"
        f'- Use the next free task id: create state/tasks/task_{task_id}.json (type "chore", '
        'role "architect", owner "agent", branch equal to your branch name) and '
        f"context/tasks/task_{task_id}_context.json (fill files_touched with `python -m "
        f"scripts.check_task_delta --base origin/main --write task_{task_id}`).\n"
        "- Do not touch .gitlab-ci.yml, AGENTS.md, CLAUDE.md, CODEOWNERS, state/config.json, "
        "state/equivalent_mutants.json or deploy/. Do not change any file under src/ or scripts/.\n"
        "- Write everything in English.\n"
        "Open the merge request when the change is ready."
    )


class Api:
    """The few GitLab endpoints the demo reads and writes."""

    def __init__(
        self,
        api_url: str,
        project: str,
        token: str,
        get_json: Callable[[str], Any] | None = None,
        send: Callable[[str, str, Mapping[str, str], Mapping[str, Any]], Any] | None = None,
    ) -> None:
        self._base = api_url.rstrip("/")
        self._project = f"{self._base}/projects/{project}"
        self._headers = {"PRIVATE-TOKEN": token, "Content-Type": "application/json"}
        self._get_json = get_json or (lambda url: _request("GET", url, self._headers, None))
        self._send = send or _request_with_body

    def variable_keys(self) -> set[str]:
        rows = self._get_json(f"{self._project}/variables?per_page={PAGE_SIZE}")
        return {row["key"] for row in rows}

    def set_variable(self, key: str, value: str) -> None:
        """Update the variable; create it, unmasked and unprotected, if it does not exist."""
        url = f"{self._project}/variables/{urllib.parse.quote(key)}"
        try:
            self._send("PUT", url, self._headers, {"value": value})
        except FactsError as error:
            if "404" not in str(error):
                raise
            body = {"key": key, "value": value, "protected": False, "masked": False}
            self._send("POST", f"{self._project}/variables", self._headers, body)

    def user_id(self, username: str) -> int:
        users = self._get_json(f"{self._base}/users?username={urllib.parse.quote(username)}")
        if not users:
            raise FactsError(f"no user named {username}")
        return int(users[0]["id"])

    def create_issue(
        self, title: str, description: str, assignee_id: int, labels: str
    ) -> Mapping[str, Any]:
        body = {
            "title": title,
            "description": description,
            "assignee_ids": [assignee_id],
            "labels": labels,
        }
        created: Mapping[str, Any] = self._send(
            "POST", f"{self._project}/issues", self._headers, body
        )
        return created

    def open_issues_with_label(self, label: str) -> list[Mapping[str, Any]]:
        rows: list[Mapping[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            query = f"state=opened&labels={label}&per_page={PAGE_SIZE}&page={page}"
            url = f"{self._project}/issues?{query}"
            chunk = self._get_json(url)
            rows += chunk
            if len(chunk) < PAGE_SIZE:
                break
        return rows

    def close_issue(self, iid: int, note: str) -> None:
        self._send("POST", f"{self._project}/issues/{iid}/notes", self._headers, {"body": note})
        self._send("PUT", f"{self._project}/issues/{iid}", self._headers, {"state_event": "close"})


def _open(request: urllib.request.Request) -> Any:
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raise FactsError(f"GitLab refused the request: HTTP {error.code}") from None
    except urllib.error.URLError as error:
        raise FactsError(f"GitLab did not answer: {error.reason}") from None


def _request(method: str, url: str, headers: Mapping[str, str], body: Any) -> Any:
    return _open(urllib.request.Request(url, headers=dict(headers), method=method))


def _request_with_body(
    method: str, url: str, headers: Mapping[str, str], body: Mapping[str, Any]
) -> Any:
    data = json.dumps(body).encode()
    return _open(urllib.request.Request(url, data=data, headers=dict(headers), method=method))


def on(api: Any, issues: int, stamp: str) -> int:
    """Turn the hands-off switch on and open ``issues`` demo issues for the Developer Flow."""
    try:
        missing = [key for key in REQUIRED if key not in api.variable_keys()]
        if missing:
            print(f"demo on: CI/CD variable(s) missing: {', '.join(missing)}", file=sys.stderr)
            return 2
        assignee = api.user_id(FLOW_USERNAME)
        api.set_variable(SWITCH, "true")
        print(
            f"{SWITCH} is true: merge_guard may take a flow's merge request out of Draft and merge"
        )
        for n in range(1, issues + 1):
            file_name = f"demo-run-{stamp}-{n}"
            task_id = f"{900 + n:03d}"
            issue = api.create_issue(
                f"demo: write docs/submission/{file_name}.md (hands-off run {n})",
                _issue_text(file_name, task_id),
                assignee,
                DEMO_LABEL,
            )
            print(f"opened {issue['web_url']} for {FLOW_USERNAME}")
    except (FactsError, KeyError) as error:
        print(f"demo on: {error}", file=sys.stderr)
        return 2
    return 0


def off(api: Any) -> int:
    """Turn the switch off and close the open demo and autoheal issues."""
    try:
        api.set_variable(SWITCH, "false")
        print(f"{SWITCH} is false: nothing else merges by itself; the demo is off")
        for label in CLOSE_LABELS:
            for issue in api.open_issues_with_label(label):
                api.close_issue(issue["iid"], "Closed by `demo off`.")
                print(f"closed issue #{issue['iid']} ({label})")
    except (FactsError, KeyError) as error:
        print(f"demo off: {error}", file=sys.stderr)
        return 2
    return 0


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("on", help="turn the switch on and open the demo issues")
    start.add_argument("--issues", type=int, default=1, help="how many demo issues to open")
    sub.add_parser("off", help="turn the switch off and close the demo issues")
    args = parser.parse_args(argv)
    token = (os.environ if env is None else env).get("GITLAB_TOKEN")
    if not token:
        print("demo: set GITLAB_TOKEN (scope api) in the environment", file=sys.stderr)
        return 2
    api = Api(API_URL, PROJECT, token)
    if args.command == "on":
        return on(api, args.issues, datetime.now().strftime("%Y%m%d-%H%M"))
    return off(api)


if __name__ == "__main__":
    raise SystemExit(main())
