"""Tests for the uvicorn entry point: the module-level app is built from the environment."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _reload_main() -> FastAPI:
    import afaw_web.main as main

    app: FastAPI = importlib.reload(main).app
    return app


@pytest.mark.characterization(
    reason="the entry point already did this; the test pins it so a change is noticed"
)
def test_main_exposes_a_fastapi_app_named_after_the_project(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> None:
    monkeypatch.setenv("AFAW_WEB_DATA_DIR", str(data_dir))
    app = _reload_main()
    assert isinstance(app, FastAPI)
    assert app.title == "AFAW Hands-off"
    assert app.docs_url is None and app.redoc_url is None


@pytest.mark.characterization(
    reason="the entry point already did this; the test pins it so a change is noticed"
)
def test_main_app_serves_the_data_directory_named_in_the_environment(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> None:
    monkeypatch.setenv("AFAW_WEB_DATA_DIR", str(data_dir))
    client = TestClient(_reload_main())
    assert client.get("/health").json() == {"status": "ok"}
    assert "live dashboard" in client.get("/").text


@pytest.mark.characterization(
    reason="the entry point already did this; the test pins it so a change is noticed"
)
def test_main_app_without_data_fails_loudly_with_503(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AFAW_WEB_DATA_DIR", str(tmp_path / "nothing-here"))
    response = TestClient(_reload_main()).get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


@pytest.mark.characterization(
    reason="the entry point already did this; the test pins it so a change is noticed"
)
def test_main_app_registers_exactly_the_documented_get_routes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AFAW_WEB_DATA_DIR", str(tmp_path))
    app = _reload_main()
    routes = {
        (path, method)
        for route in app.routes
        for path in [getattr(route, "path", "")]
        for method in getattr(route, "methods", None) or ()
        if path in {"/", "/live/", "/health", "/api/state", "/api/ask"}
    }
    assert routes == {
        ("/", "GET"),
        ("/live/", "GET"),
        ("/health", "GET"),
        ("/api/state", "GET"),
        ("/api/ask", "GET"),
    }
