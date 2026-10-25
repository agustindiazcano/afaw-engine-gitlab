"""The monitor stage: verify that the live service answers and serves the derived views.

It requests /health (must be 200 with status ok) and /api/state (must hold the three derived
views). With ``--expect-sha`` it also requires /api/version to report exactly that commit, which
proves that the revision serving traffic is the one just deployed; with ``--page`` (repeatable) it
requires each page to answer 200. An unreachable service, a wrong status or a missing view fails
loudly; it never reports a pass for something it could not reach. A cold start of a scale-to-zero
service is covered by retries with exponential backoff.

Run in CI: python -m scripts.check_live --url "$GCP_SERVICE_URL" --expect-sha "$CI_COMMIT_SHA"
With ``--json PATH`` it also writes the base URL, the expected sha, the status of every checked
path and a boolean ok to that file, whether the check passes or fails; the exit code is the same.

Exit codes: 0 ok, 1 the service is not healthy, 2 the arguments are invalid.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

TIMEOUT_SECONDS = 20
VIEWS = ("metrics", "pending", "history")
LOCAL_HOSTS = ("127.0.0.1", "localhost")


def _get(url: str) -> tuple[int, Any]:
    """GET a URL; return the status and the decoded JSON body."""
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, None


def _status(url: str) -> int:
    """GET a URL and return only the status code."""
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return exc.code


def version_problems(base: str, expect_sha: str) -> list[str]:
    """Why /api/version does not report the commit that was just deployed (empty when it does)."""
    status, body = _get(f"{base}/api/version")
    if status != 200 or not isinstance(body, dict):
        return [f"/api/version answered {status} instead of 200 with the commit"]
    reported = body.get("commit_sha")
    if reported != expect_sha:
        return [f"/api/version commit_sha is {reported!r}, expected {expect_sha!r}"]
    return []


def problems(
    base: str,
    expect_sha: str | None = None,
    pages: tuple[str, ...] = (),
    statuses: dict[str, int | None] | None = None,
) -> list[str]:
    """What is wrong with the service at ``base`` right now (empty when it is healthy).

    When ``statuses`` is given it is filled with the HTTP status of /health, /api/state and each
    page (None for a path that never answered).
    """
    found: list[str] = []
    seen = statuses if statuses is not None else {}
    seen.clear()
    seen.update({path: None for path in ("/health", "/api/state", *pages)})
    try:
        status, body = _get(f"{base}/health")
        seen["/health"] = status
        if status != 200 or not isinstance(body, dict) or body.get("status") != "ok":
            found.append(f"/health answered {status} instead of 200 with status ok")
        status, body = _get(f"{base}/api/state")
        seen["/api/state"] = status
        if status != 200 or not isinstance(body, dict):
            found.append(f"/api/state answered {status} instead of 200 with the views")
        else:
            found += [f"/api/state lacks the {v} view" for v in VIEWS if v not in body]
        if expect_sha:
            found += version_problems(base, expect_sha)
        for page in pages:
            status = _status(f"{base}{page}")
            seen[page] = status
            if status != 200:
                found.append(f"{page} answered {status} instead of 200")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        found.append(f"the service did not answer ({exc!r})")
    return found


def write_result(
    path: str, base: str, expect_sha: str | None, statuses: dict[str, int | None], ok: bool
) -> None:
    """Write the JSON result of the check to ``path``."""
    result = {"base_url": base, "expected_sha": expect_sha, "statuses": statuses, "ok": ok}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    """Check /health and /api/state of the live service, with retries for a cold start."""
    parser = argparse.ArgumentParser(description="Verify the live AFAW service.")
    parser.add_argument("--url", required=True, help="base URL of the service")
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--wait", type=float, default=3.0, help="first backoff in seconds")
    parser.add_argument("--expect-sha", help="the commit /api/version must report")
    parser.add_argument("--page", action="append", default=[], help="a page that must answer 200")
    parser.add_argument("--json", metavar="PATH", help="also write the result to this JSON file")
    args = parser.parse_args(argv)
    parts = urlsplit(args.url)
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in LOCAL_HOSTS):
        sys.stderr.write("ERROR: --url must be https (http only for a local address)\n")
        return 2
    base = args.url.rstrip("/")
    found: list[str] = []
    statuses: dict[str, int | None] = {}
    for attempt in range(args.attempts):
        found = problems(base, args.expect_sha, tuple(args.page), statuses)
        if not found:
            break
        if attempt + 1 < args.attempts:
            time.sleep(args.wait * 2**attempt)
    if args.json:
        write_result(args.json, base, args.expect_sha, statuses, not found)
    if not found:
        sys.stdout.write(f"OK: {base} answers /health and serves the derived views\n")
        return 0
    for item in found:
        sys.stderr.write(f"PROBLEM: {item}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
