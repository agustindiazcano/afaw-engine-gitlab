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


def test_root_serves_this_repositorys_real_dashboard(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200 and "live dashboard" in response.text
    assert "demo dashboard" not in response.text


def test_the_demo_with_invented_data_moved_to_its_own_path(client: TestClient) -> None:
    response = client.get("/demo/")
    assert response.status_code == 200 and "demo dashboard" in response.text


def test_the_experiments_and_environment_pages_are_served_from_the_live_views(
    client: TestClient,
) -> None:
    assert client.get("/experiments/").text == "<html>experiments page</html>"
    assert client.get("/environment/").text == "<html>environment page</html>"
    assert client.get("/experiments/").headers["content-type"].startswith("text/html")


@pytest.mark.parametrize(
    ("path", "name"),
    [("/experiments/", "experiments.html"), ("/environment/", "environment.html")],
)
def test_a_missing_statistics_page_is_503_and_never_breaks_the_health_check(
    data_dir: Path, path: str, name: str
) -> None:
    (data_dir / "live" / name).unlink()
    client = TestClient(create_app(Settings(data_dir=data_dir)))
    response = client.get(path)
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "missing": [f"live/{name}"]}
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_the_old_live_path_still_serves_the_same_real_dashboard(client: TestClient) -> None:
    assert client.get("/live/").text == client.get("/").text


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
@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/demo/",
        "/live/",
        "/experiments/",
        "/environment/",
        "/health",
        "/api/state",
        "/api/ask",
    ],
)
def test_the_service_is_read_only(client: TestClient, method: str, path: str) -> None:
    assert getattr(client, method)(path).status_code == 405


def test_requests_never_change_the_data_directory(client: TestClient, data_dir: Path) -> None:
    before = sorted((p, p.stat().st_mtime_ns) for p in data_dir.rglob("*") if p.is_file())
    for path in ("/", "/demo/", "/live/", "/health", "/api/state", "/api/ask?q=mutation"):
        client.get(path)
    assert before == sorted((p, p.stat().st_mtime_ns) for p in data_dir.rglob("*") if p.is_file())


@pytest.mark.characterization(
    reason="the 503 for a missing page already existed; the test pins it so a change is noticed"
)
@pytest.mark.parametrize(
    ("path", "missing"),
    [
        ("/demo/", "demo/index.html"),
        ("/live/", "live/dashboard.html"),
        ("/", "live/dashboard.html"),
    ],
)
def test_a_missing_page_is_503_and_names_the_file(data_dir: Path, path: str, missing: str) -> None:
    (data_dir / missing).unlink()
    response = TestClient(create_app(Settings(data_dir=data_dir))).get(path)
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "missing": [missing]}


def _client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir)))


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
@pytest.mark.parametrize("name", ["live/metrics.json", "live/pending.json", "live/history.json"])
def test_state_names_exactly_the_missing_view_in_its_503_body(data_dir: Path, name: str) -> None:
    (data_dir / name).unlink()
    response = _client(data_dir).get("/api/state")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "missing": [name]}


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_state_lists_every_missing_view_in_a_fixed_order(data_dir: Path) -> None:
    shutil.rmtree(data_dir / "live")
    response = _client(data_dir).get("/api/state")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "missing": ["live/metrics.json", "live/pending.json", "live/history.json"],
    }


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_state_ignores_a_missing_html_page(data_dir: Path) -> None:
    (data_dir / "live" / "dashboard.html").unlink()
    (data_dir / "demo" / "index.html").unlink()
    response = _client(data_dir).get("/api/state")
    assert response.status_code == 200
    assert set(response.json()) == {"metrics", "pending", "history"}


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_state_has_exactly_three_keys_in_a_fixed_order(client: TestClient) -> None:
    assert list(client.get("/api/state").json()) == ["metrics", "pending", "history"]


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_state_is_json(client: TestClient) -> None:
    assert client.get("/api/state").headers["content-type"] == "application/json"


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_state_reads_utf8_views(data_dir: Path) -> None:
    (data_dir / "live" / "history.json").write_text('[{"id": "tâche_é"}]', encoding="utf-8")
    assert _client(data_dir).get("/api/state").json()["history"] == [{"id": "tâche_é"}]


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_health_ok_body_is_exactly_status_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
    assert response.headers["content-type"] == "application/json"


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
@pytest.mark.parametrize(
    "name",
    [
        "live/metrics.json",
        "live/pending.json",
        "live/history.json",
        "live/dashboard.html",
        "demo/index.html",
    ],
)
def test_health_names_exactly_the_one_missing_file(data_dir: Path, name: str) -> None:
    (data_dir / name).unlink()
    response = _client(data_dir).get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "missing": [name]}


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_health_lists_all_missing_files_in_a_fixed_order(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/health")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "missing": [
            "live/metrics.json",
            "live/pending.json",
            "live/history.json",
            "live/dashboard.html",
            "demo/index.html",
        ],
    }


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_health_treats_a_directory_as_missing(data_dir: Path) -> None:
    (data_dir / "live" / "metrics.json").unlink()
    (data_dir / "live" / "metrics.json").mkdir()
    response = _client(data_dir).get("/health")
    assert response.status_code == 503
    assert response.json()["missing"] == ["live/metrics.json"]


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_a_missing_view_is_logged_as_an_error(
    data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (data_dir / "live" / "pending.json").unlink()
    with caplog.at_level("DEBUG", logger="afaw_web"):
        _client(data_dir).get("/health")
    records = [r for r in caplog.records if r.name == "afaw_web"]
    assert len(records) == 1
    assert records[0].levelname == "ERROR"
    assert records[0].getMessage() == "data missing: ['live/pending.json']"


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_a_healthy_request_logs_nothing(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("DEBUG", logger="afaw_web"):
        client.get("/health")
        client.get("/api/state")
    assert [r for r in caplog.records if r.name == "afaw_web"] == []


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_demo_serves_the_demo_page_verbatim_as_html(client: TestClient) -> None:
    response = client.get("/demo/")
    assert response.text == "<html>demo dashboard</html>"
    assert response.headers["content-type"].startswith("text/html")


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_live_serves_the_live_page_verbatim_as_html(client: TestClient) -> None:
    response = client.get("/live/")
    assert response.text == "<html>live dashboard</html>"
    assert response.headers["content-type"].startswith("text/html")


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_pages_are_read_as_utf8(data_dir: Path) -> None:
    (data_dir / "demo" / "index.html").write_text("<p>métrica ñ ✓</p>", encoding="utf-8")
    (data_dir / "live" / "dashboard.html").write_text("<p>tâche ü ✓</p>", encoding="utf-8")
    client = _client(data_dir)
    assert client.get("/demo/").text == "<p>métrica ñ ✓</p>"
    assert client.get("/").text == "<p>tâche ü ✓</p>"
    assert client.get("/live/").text == "<p>tâche ü ✓</p>"


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_demo_is_503_naming_the_missing_demo_page(data_dir: Path) -> None:
    (data_dir / "demo" / "index.html").unlink()
    response = _client(data_dir).get("/demo/")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "missing": ["demo/index.html"]}


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_live_is_503_naming_the_missing_live_page(data_dir: Path) -> None:
    (data_dir / "live" / "dashboard.html").unlink()
    response = _client(data_dir).get("/live/")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "missing": ["live/dashboard.html"]}


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_each_page_works_without_the_other(data_dir: Path) -> None:
    (data_dir / "demo" / "index.html").unlink()
    assert _client(data_dir).get("/").status_code == 200
    assert _client(data_dir).get("/live/").status_code == 200
    (data_dir / "demo" / "index.html").write_text("<html>demo</html>", encoding="utf-8")
    (data_dir / "live" / "dashboard.html").unlink()
    assert _client(data_dir).get("/demo/").status_code == 200


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_ask_returns_exactly_the_documented_shape(client: TestClient) -> None:
    body = client.get("/api/ask", params={"q": "mutation gate"}).json()
    assert list(body) == ["query", "message", "results"]
    assert body["query"] == "mutation gate"
    assert body["message"] == ""
    assert [list(r) for r in body["results"]] == [["path", "title", "excerpts", "score"]]
    assert body["results"][0] == {
        "path": "docs/adr/0001-coverage.md",
        "title": "Measured coverage is 80% of lines",
        "excerpts": ["The mutation gate requires 80.0 percent."],
        "score": 2,
    }


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_ask_no_match_message_is_exact(client: TestClient) -> None:
    assert client.get("/api/ask", params={"q": "kubernetes"}).json() == {
        "query": "kubernetes",
        "message": "no record contains any word of the question",
        "results": [],
    }


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_ask_echoes_the_question_unchanged(client: TestClient) -> None:
    question = "  Mutation GATE? "
    assert client.get("/api/ask", params={"q": question}).json()["query"] == question


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
@pytest.mark.parametrize("length", [1, 2, 199, 200])
def test_ask_accepts_questions_up_to_the_200_character_limit(
    client: TestClient, length: int
) -> None:
    response = client.get("/api/ask", params={"q": "x" * length})
    assert response.status_code == 200
    assert len(response.json()["query"]) == length


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_ask_rejects_201_characters_and_the_empty_question(client: TestClient) -> None:
    too_long = client.get("/api/ask", params={"q": "x" * 201})
    assert too_long.status_code == 422
    assert too_long.json()["detail"][0]["type"] == "string_too_long"
    assert too_long.json()["detail"][0]["ctx"] == {"max_length": 200}
    empty = client.get("/api/ask", params={"q": ""})
    assert empty.status_code == 422
    assert empty.json()["detail"][0]["type"] == "string_too_short"
    assert empty.json()["detail"][0]["ctx"] == {"min_length": 1}
    missing = client.get("/api/ask")
    assert missing.status_code == 422
    assert missing.json()["detail"][0]["type"] == "missing"


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_ask_still_answers_when_a_view_is_missing(data_dir: Path) -> None:
    shutil.rmtree(data_dir / "live" / "context")
    (data_dir / "live" / "metrics.json").unlink()
    response = _client(data_dir).get("/api/ask", params={"q": "mutation"})
    assert response.status_code == 200
    assert response.json()["results"][0]["path"] == "docs/adr/0001-coverage.md"


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_the_interactive_docs_are_not_exposed(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_the_openapi_schema_names_the_app_and_lists_only_get_routes(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "AFAW Hands-off"
    assert set(schema["paths"]) == {
        "/health",
        "/api/state",
        "/api/version",
        "/",
        "/demo/",
        "/live/",
        "/experiments/",
        "/environment/",
        "/api/ask",
    }
    assert all(set(methods) == {"get"} for methods in schema["paths"].values())


@pytest.mark.characterization(
    reason="the code already did this; the test pins it so a change is noticed"
)
def test_ask_parameter_limits_are_in_the_schema(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    parameter = schema["paths"]["/api/ask"]["get"]["parameters"][0]
    assert parameter["name"] == "q" and parameter["required"] is True
    assert parameter["schema"]["minLength"] == 1
    assert parameter["schema"]["maxLength"] == 200
