"""Tests for scripts.check_live: the monitor stage fails loudly if the live service is wrong."""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
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


@contextmanager
def _server(routes: dict[str, tuple[int, Any]]) -> Iterator[str]:
    """A fake service that stays up for the whole ``with`` block."""
    yield from _serve(routes)


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
    with _server(routes) as url:
        assert _run(url) == 1
    err = capsys.readouterr().err
    assert "/health answered 503" in err and "did not answer" not in err


def test_a_state_without_the_derived_views_fails() -> None:
    routes = {"/health": (200, {"status": "ok"}), "/api/state": (200, {"metrics": {}})}
    with _server(routes) as url:
        assert _run(url) == 1


def test_no_answer_fails_after_the_attempts(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run("http://127.0.0.1:9") == 1
    assert "PROBLEM" in capsys.readouterr().err


def test_a_url_that_is_not_https_or_local_http_is_refused() -> None:
    assert check_live.main(["--url", "ftp://example.com", "--attempts", "1", "--wait", "0"]) == 2


# ---- the deployed commit and the pages


def _healthy_routes(**extra: tuple[int, Any]) -> dict[str, tuple[int, Any]]:
    return {"/health": (200, {"status": "ok"}), "/api/state": (200, STATE), **extra}


def _run_with(url: str, *args: str) -> int:
    return check_live.main(["--url", url, "--attempts", "1", "--wait", "0", *args])


def test_the_expected_commit_passes_when_the_service_reports_it() -> None:
    version = {"release_tag": "v0.9", "commit_sha": "abc123"}
    with _server(_healthy_routes(**{"/api/version": (200, version)})) as url:
        assert _run_with(url, "--expect-sha", "abc123") == 0


def test_a_service_running_another_commit_fails_and_says_which(
    capsys: pytest.CaptureFixture[str],
) -> None:
    version = {"release_tag": "v0.9", "commit_sha": "old000"}
    with _server(_healthy_routes(**{"/api/version": (200, version)})) as url:
        assert _run_with(url, "--expect-sha", "abc123") == 1
    err = capsys.readouterr().err
    assert "commit_sha" in err and "old000" in err and "abc123" in err


def test_a_service_that_reports_unknown_fails_the_expected_commit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    version = {"release_tag": "unknown", "commit_sha": "unknown"}
    with _server(_healthy_routes(**{"/api/version": (200, version)})) as url:
        assert _run_with(url, "--expect-sha", "abc123") == 1
    assert "unknown" in capsys.readouterr().err


def test_a_service_without_the_version_endpoint_fails_the_expected_commit() -> None:
    with _server(_healthy_routes()) as url:
        assert _run_with(url, "--expect-sha", "abc123") == 1


@pytest.mark.characterization(
    reason="the version was never read before; this pins that it still is not without the flag"
)
def test_without_an_expected_commit_the_version_is_not_looked_at() -> None:
    with _server(_healthy_routes()) as url:
        assert _run_with(url) == 0


def test_pages_that_answer_200_pass() -> None:
    routes = _healthy_routes(**{"/": (200, {}), "/experiments/": (200, {})})
    with _server(routes) as url:
        assert _run_with(url, "--page", "/", "--page", "/experiments/") == 0


def test_a_missing_page_fails_and_names_it(capsys: pytest.CaptureFixture[str]) -> None:
    routes = _healthy_routes(**{"/": (200, {})})
    with _server(routes) as url:
        assert _run_with(url, "--page", "/", "--page", "/environment/") == 1
    assert "/environment/ answered 404" in capsys.readouterr().err


# ---- the optional JSON result file


def test_the_json_file_records_the_statuses_of_a_healthy_service(tmp_path: Path) -> None:
    out = tmp_path / "result.json"
    routes = _healthy_routes(**{"/": (200, {}), "/api/version": (200, {"commit_sha": "abc123"})})
    with _server(routes) as url:
        assert _run_with(url, "--page", "/", "--expect-sha", "abc123", "--json", str(out)) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == {
        "base_url": url,
        "expected_sha": "abc123",
        "statuses": {"/health": 200, "/api/state": 200, "/": 200},
        "ok": True,
    }


def test_the_json_file_is_written_when_the_check_fails_and_the_exit_code_stays(
    tmp_path: Path,
) -> None:
    out = tmp_path / "result.json"
    routes = {"/health": (503, {"status": "unavailable"}), "/api/state": (200, STATE)}
    with _server(routes) as url:
        assert _run_with(url, "--page", "/missing/", "--json", str(out)) == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["ok"] is False
    assert data["expected_sha"] is None
    assert data["statuses"] == {"/health": 503, "/api/state": 200, "/missing/": 404}


def test_the_json_file_is_written_when_the_service_does_not_answer(tmp_path: Path) -> None:
    out = tmp_path / "result.json"
    assert _run_with("http://127.0.0.1:9", "--json", str(out)) == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["ok"] is False
    assert data["statuses"].get("/health") is None


@pytest.mark.characterization(reason="without the flag no file was ever written; pins that")
def test_no_json_file_is_written_without_the_flag(tmp_path: Path, healthy: str) -> None:
    assert _run_with(healthy) == 0
    assert list(tmp_path.iterdir()) == []


# ---- a newer deploy that overtook this pipeline (concurrent pipelines of main)


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, timeout=30
    )
    return done.stdout.strip()


@pytest.fixture
def history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """A repo with commits ``old`` <- ``new`` on main and an unrelated ``side`` branch."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "old")
    old = _git(repo, "rev-parse", "HEAD")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "new")
    new = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side", old)
    _git(repo, "commit", "-q", "--allow-empty", "-m", "side")
    side = _git(repo, "rev-parse", "HEAD")
    monkeypatch.chdir(repo)
    return {"old": old, "new": new, "side": side}


def _version(sha: str) -> dict[str, tuple[int, Any]]:
    return _healthy_routes(**{"/api/version": (200, {"commit_sha": sha})})


def test_a_service_running_a_newer_commit_passes(
    history: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    with _server(_version(history["new"])) as url:
        assert _run_with(url, "--expect-sha", history["old"]) == 0
    assert "newer" in capsys.readouterr().out


@pytest.mark.characterization(reason="a mismatch always failed; pins that it still does")
def test_a_service_running_an_older_commit_still_fails(history: dict[str, str]) -> None:
    with _server(_version(history["old"])) as url:
        assert _run_with(url, "--expect-sha", history["new"]) == 1


@pytest.mark.characterization(reason="a mismatch always failed; pins that it still does")
def test_a_service_running_an_unrelated_commit_still_fails(history: dict[str, str]) -> None:
    with _server(_version(history["side"])) as url:
        assert _run_with(url, "--expect-sha", history["new"]) == 1


@pytest.mark.characterization(reason="a mismatch always failed; pins that it still does")
def test_an_unknown_reported_commit_fails_even_with_history(history: dict[str, str]) -> None:
    with _server(_version("unknown")) as url:
        assert _run_with(url, "--expect-sha", history["old"]) == 1


@pytest.mark.characterization(reason="a mismatch always failed; pins that it still does")
def test_a_newer_commit_fails_closed_without_a_git_repository(
    history: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "no-repo"
    empty.mkdir()
    monkeypatch.chdir(empty)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    with _server(_version(history["new"])) as url:
        assert _run_with(url, "--expect-sha", history["old"]) == 1
