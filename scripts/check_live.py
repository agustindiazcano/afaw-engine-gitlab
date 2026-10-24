"""The monitor stage: verify that the live service answers and serves the derived views.

It requests /health (must be 200 with status ok) and /api/state (must hold the three derived
views). An unreachable service, a wrong status or a missing view fails loudly; it never reports a
pass for something it could not reach. A cold start of a scale-to-zero service is covered by
retries with exponential backoff.

Run in CI: python -m scripts.check_live --url "$GCP_SERVICE_URL"
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


def problems(base: str) -> list[str]:
    """What is wrong with the service at ``base`` right now (empty when it is healthy)."""
    found: list[str] = []
    try:
        status, body = _get(f"{base}/health")
        if status != 200 or not isinstance(body, dict) or body.get("status") != "ok":
            found.append(f"/health answered {status} instead of 200 with status ok")
        status, body = _get(f"{base}/api/state")
        if status != 200 or not isinstance(body, dict):
            found.append(f"/api/state answered {status} instead of 200 with the views")
        else:
            found += [f"/api/state lacks the {v} view" for v in VIEWS if v not in body]
    except (urllib.error.URLError, OSError, ValueError) as exc:
        found.append(f"the service did not answer ({exc!r})")
    return found


def main(argv: list[str] | None = None) -> int:
    """Check /health and /api/state of the live service, with retries for a cold start."""
    parser = argparse.ArgumentParser(description="Verify the live AFAW service.")
    parser.add_argument("--url", required=True, help="base URL of the service")
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--wait", type=float, default=3.0, help="first backoff in seconds")
    args = parser.parse_args(argv)
    parts = urlsplit(args.url)
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in LOCAL_HOSTS):
        sys.stderr.write("ERROR: --url must be https (http only for a local address)\n")
        return 2
    base = args.url.rstrip("/")
    found: list[str] = []
    for attempt in range(args.attempts):
        found = problems(base)
        if not found:
            sys.stdout.write(f"OK: {base} answers /health and serves the derived views\n")
            return 0
        if attempt + 1 < args.attempts:
            time.sleep(args.wait * 2**attempt)
    for item in found:
        sys.stderr.write(f"PROBLEM: {item}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
