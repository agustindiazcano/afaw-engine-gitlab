"""Tests for GET /api/version: release tag and commit sha come from the environment only."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_version_returns_both_values_exactly_as_set(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AFAW_RELEASE_TAG", "v0.10")
    monkeypatch.setenv("AFAW_COMMIT_SHA", "0123abc")
    response = client.get("/api/version")
    assert response.status_code == 200
    assert response.json() == {"release_tag": "v0.10", "commit_sha": "0123abc"}


def test_version_is_unknown_when_the_variables_are_unset(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AFAW_RELEASE_TAG", raising=False)
    monkeypatch.delenv("AFAW_COMMIT_SHA", raising=False)
    response = client.get("/api/version")
    assert response.status_code == 200
    assert response.json() == {"release_tag": "unknown", "commit_sha": "unknown"}


def test_version_treats_an_empty_variable_as_unknown(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AFAW_RELEASE_TAG", "")
    monkeypatch.setenv("AFAW_COMMIT_SHA", "0123abc")
    assert client.get("/api/version").json() == {
        "release_tag": "unknown",
        "commit_sha": "0123abc",
    }
    monkeypatch.setenv("AFAW_RELEASE_TAG", "v0.10")
    monkeypatch.setenv("AFAW_COMMIT_SHA", "")
    assert client.get("/api/version").json() == {
        "release_tag": "v0.10",
        "commit_sha": "unknown",
    }


def test_version_rejects_post_with_405(client: TestClient) -> None:
    assert client.post("/api/version").status_code == 405


def test_version_is_in_the_openapi_description_with_a_summary(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"]["/api/version"]["get"]
    assert operation["summary"]
    assert "\n" not in operation["summary"]
