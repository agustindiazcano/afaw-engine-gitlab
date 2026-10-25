"""Validation of the q parameter of /api/ask: 1 to 200 characters after trimming whitespace."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient


def _assert_names_q(response: Any) -> None:
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    errors = response.json()["detail"]
    assert errors and all(error["loc"][-1] == "q" for error in errors)
    assert all(error["msg"].startswith("q:") for error in errors)


def test_ask_without_q_is_422_and_names_q(client: TestClient) -> None:
    _assert_names_q(client.get("/api/ask"))


@pytest.mark.parametrize("q", ["", " ", "   ", "\t\n "])
def test_ask_with_an_empty_or_whitespace_only_q_is_422_and_names_q(
    client: TestClient, q: str
) -> None:
    _assert_names_q(client.get("/api/ask", params={"q": q}))


def test_ask_with_201_characters_is_422_and_names_q(client: TestClient) -> None:
    _assert_names_q(client.get("/api/ask", params={"q": "x" * 201}))


def test_ask_with_201_characters_after_trimming_is_422(client: TestClient) -> None:
    _assert_names_q(client.get("/api/ask", params={"q": f" {'x' * 201} "}))


@pytest.mark.characterization(reason="200 characters were already accepted before the change")
def test_ask_accepts_exactly_200_characters(client: TestClient) -> None:
    response = client.get("/api/ask", params={"q": "x" * 200})
    assert response.status_code == 200 and response.json()["query"] == "x" * 200


def test_ask_counts_the_characters_after_trimming_whitespace(client: TestClient) -> None:
    padded = f"  {'x' * 200}  "
    response = client.get("/api/ask", params={"q": padded})
    assert response.status_code == 200 and response.json()["query"] == padded


@pytest.mark.characterization(reason="a normal query already returned this response")
def test_ask_normal_query_response_is_unchanged(client: TestClient) -> None:
    body = client.get("/api/ask", params={"q": "mutation gate"}).json()
    assert body["query"] == "mutation gate" and body["message"] == ""
    assert set(body) == {"query", "message", "results"}
    assert body["results"][0]["path"] == "docs/adr/0001-coverage.md"
    assert set(body["results"][0]) == {"path", "title", "excerpts", "score"}


def test_the_openapi_description_documents_the_limit(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"]["/api/ask"]["get"]
    description = operation["parameters"][0]["description"]
    assert "1" in description and "200" in description and "whitespace" in description
