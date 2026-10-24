"""Tests for scripts.check_live: the monitor stage fails loudly if the live service is wrong."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from scripts import check_live

STATE = {"metrics": {"as_of": "x"}, "pending": [], "history": []}


def _serve(routes: dict[str, tuple[int, Any]]) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            status, body = routes.get(self.path, (404, {}))
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()


@pytest.fixture
def healthy() -> Iterator[str]:
    yield from _serve({"/health": (200, {"status": "ok"}), "/api/state": (200, STATE)})


def _run(url: str) -> int:
    return check_live.main(["--url", url, "--attempts", "2", "--wait", "0"])


def test_a_healthy_service_passes(healthy: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(healthy) == 0
    assert "OK" in capsys.readouterr().out


def test_an_unhealthy_service_fails_loudly(capsys: pytest.CaptureFixture[str]) -> None:
    routes = {"/health": (503, {"status": "unavailable"}), "/api/state": (200, STATE)}
    url = next(_serve(routes))
    assert _run(url) == 1
    assert "PROBLEM" in capsys.readouterr().err


def test_a_state_without_the_derived_views_fails() -> None:
    url = next(_serve({"/health": (200, {"status": "ok"}), "/api/state": (200, {"metrics": {}})}))
    assert _run(url) == 1


def test_no_answer_fails_after_the_attempts(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run("http://127.0.0.1:9") == 1
    assert "PROBLEM" in capsys.readouterr().err


def test_a_url_that_is_not_https_or_local_http_is_refused() -> None:
    assert check_live.main(["--url", "ftp://example.com", "--attempts", "1", "--wait", "0"]) == 2
