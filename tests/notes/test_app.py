"""Tests for the notes demo app: the target the Duo flows change, deployed on its own."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from notes_app.app import MAX_NOTES, MAX_TEXT, create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def test_health_is_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_comes_from_the_environment(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AFAW_RELEASE_TAG", "v0.7")
    monkeypatch.setenv("AFAW_COMMIT_SHA", "abc123")
    assert client.get("/api/version").json() == {"release_tag": "v0.7", "commit_sha": "abc123"}


def test_version_is_unknown_when_unset(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AFAW_RELEASE_TAG", raising=False)
    monkeypatch.delenv("AFAW_COMMIT_SHA", raising=False)
    assert client.get("/api/version").json() == {
        "release_tag": "unknown",
        "commit_sha": "unknown",
    }


def test_notes_start_empty(client: TestClient) -> None:
    assert client.get("/api/notes").json() == []


def test_a_note_is_created_and_listed_newest_first(client: TestClient) -> None:
    first = client.post("/api/notes", json={"text": "first"})
    second = client.post("/api/notes", json={"text": "second"})
    assert first.status_code == 201
    assert first.json() == {"id": 1, "text": "first"}
    assert second.json()["id"] == 2
    assert [n["text"] for n in client.get("/api/notes").json()] == ["second", "first"]


def test_the_text_is_trimmed(client: TestClient) -> None:
    assert client.post("/api/notes", json={"text": "  hi  "}).json()["text"] == "hi"


@pytest.mark.parametrize("text", ["", "   ", "x" * (MAX_TEXT + 1)])
def test_a_text_out_of_range_is_rejected(client: TestClient, text: str) -> None:
    assert client.post("/api/notes", json={"text": text}).status_code == 422
    assert client.get("/api/notes").json() == []


def test_a_text_of_the_maximum_length_is_accepted(client: TestClient) -> None:
    assert client.post("/api/notes", json={"text": "x" * MAX_TEXT}).status_code == 201


def test_extra_fields_are_rejected(client: TestClient) -> None:
    assert client.post("/api/notes", json={"text": "a", "done": True}).status_code == 422


def test_the_store_is_capped(client: TestClient) -> None:
    for i in range(MAX_NOTES):
        assert client.post("/api/notes", json={"text": f"n{i}"}).status_code == 201
    over = client.post("/api/notes", json={"text": "one too many"})
    assert over.status_code == 409
    assert len(client.get("/api/notes").json()) == MAX_NOTES


def test_each_app_has_its_own_store() -> None:
    a, b = TestClient(create_app()), TestClient(create_app())
    a.post("/api/notes", json={"text": "only in a"})
    assert b.get("/api/notes").json() == []


def test_the_page_names_the_app_and_loads_the_notes(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AFAW demo notes" in response.text
    assert "/api/notes" in response.text


def test_the_page_styles_the_button_with_the_brand_colour(client: TestClient) -> None:
    # The end to end tests read this colour from the rendered page, so a wrong colour is caught.
    assert "#0b5fff" in client.get("/").text
