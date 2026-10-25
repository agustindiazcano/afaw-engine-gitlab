"""Tests for the read-only AFAW web service: measured numbers are served verbatim."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from afaw_web.app import create_app
from afaw_web.settings import Settings
from tests.web.conftest import HISTORY, METRICS, PENDING


def test_health_is_ok_when_the_data_is_there(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}


def test_health_fails_loudly_when_the_data_is_missing(data_dir: Path) -> None:
    shutil.rmtree(data_dir / "live")
    response = TestClient(create_app(Settings(data_dir=data_dir))).get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert "live/metrics.json" in response.json()["missing"]


def test_state_returns_the_derived_views_verbatim(client: TestClient) -> None:
    body = client.get("/api/state").json()
    assert body == {"metrics": METRICS, "pending": PENDING, "history": HISTORY}


def test_state_is_503_when_a_view_is_missing(data_dir: Path) -> None:
    (data_dir / "live" / "metrics.json").unlink()
    response = TestClient(create_app(Settings(data_dir=data_dir))).get("/api/state")
    assert response.status_code == 503


def test_root_serves_the_demo_dashboard(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200 and "demo dashboard" in response.text


def test_live_serves_this_repositorys_dashboard(client: TestClient) -> None:
    response = client.get("/live/")
    assert response.status_code == 200 and "live dashboard" in response.text


def test_ask_cites_the_file_and_copies_the_line_verbatim(client: TestClient) -> None:
    body = client.get("/api/ask", params={"q": "mutation gate"}).json()
    top = body["results"][0]
    assert top["path"] == "docs/adr/0001-coverage.md"
    assert "The mutation gate requires 80.0 percent." in top["excerpts"]
    assert "Unrelated line." not in top["excerpts"]


def test_ask_searches_the_gotchas_and_the_last_context(client: TestClient) -> None:
    found = client.get("/api/ask", params={"q": "files_touched"}).json()["results"]
    paths = {r["path"] for r in found}
    assert paths == {"docs/gotchas/0001-delta.md"}
    last = client.get("/api/ask", params={"q": "progress"}).json()["results"]
    assert last[0]["path"] == "live/context/global/LASTCONTEXT.md"
    assert "- Progress: 10 of 10 tasks done (100%)." in last[0]["excerpts"]


def test_ask_with_no_match_returns_no_results_and_says_so(client: TestClient) -> None:
    body = client.get("/api/ask", params={"q": "kubernetes"}).json()
    assert body["results"] == [] and "no record" in body["message"]


def test_ask_is_deterministic(client: TestClient) -> None:
    first = client.get("/api/ask", params={"q": "the"}).json()
    assert client.get("/api/ask", params={"q": "the"}).json() == first


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "x" * 201}])
def test_ask_rejects_a_missing_or_oversized_question(
    client: TestClient, params: dict[str, str]
) -> None:
    assert client.get("/api/ask", params=params).status_code == 422


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
@pytest.mark.parametrize("path", ["/", "/live/", "/health", "/api/state", "/api/ask"])
def test_the_service_is_read_only(client: TestClient, method: str, path: str) -> None:
    assert getattr(client, method)(path).status_code == 405


def test_requests_never_change_the_data_directory(client: TestClient, data_dir: Path) -> None:
    before = sorted((p, p.stat().st_mtime_ns) for p in data_dir.rglob("*") if p.is_file())
    for path in ("/", "/live/", "/health", "/api/state", "/api/ask?q=mutation"):
        client.get(path)
    assert before == sorted((p, p.stat().st_mtime_ns) for p in data_dir.rglob("*") if p.is_file())


@pytest.mark.characterization(
    reason="the 503 for a missing page already existed; the test pins it so a change is noticed"
)
@pytest.mark.parametrize(
    ("path", "missing"), [("/", "demo/index.html"), ("/live/", "live/dashboard.html")]
)
def test_a_missing_page_is_503_and_names_the_file(data_dir: Path, path: str, missing: str) -> None:
    (data_dir / missing).unlink()
    response = TestClient(create_app(Settings(data_dir=data_dir))).get(path)
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "missing": [missing]}
