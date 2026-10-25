"""cost_log: one markdown row per merge request or session, measured columns only."""

from typing import Any

import pytest

from scripts import cost_log
from scripts.afaw_state.facts import GitLab

API = "https://gitlab.com/api/v4"
PROJECT = "7"


def pipeline(pid: int, created: str, sha: str = "aaa", source: str = "merge_request_event"):
    return {
        "id": pid,
        "sha": sha,
        "status": "success",
        "source": source,
        "created_at": created,
        "updated_at": created,
        "web_url": f"https://gitlab.com/g/p/-/pipelines/{pid}",
    }


def job(name: str, duration: float | None, started: bool = True) -> dict[str, Any]:
    return {
        "name": name,
        "duration": duration,
        "started_at": "2026-10-25T02:00:00Z" if started else None,
        "queued_duration": 1.0,
    }


def fake_gitlab(routes: dict[str, Any]) -> GitLab:
    def get_json(url: str) -> Any:
        path = url.removeprefix(f"{API}/projects/{PROJECT}/").split("?")[0]
        return routes[path]

    return GitLab(API, PROJECT, None, get_json=get_json)


def test_row_for_a_merge_request_has_measured_columns_and_human_credit_columns() -> None:
    gitlab = fake_gitlab(
        {
            "merge_requests/9/pipelines": [
                pipeline(1, "2026-10-25T02:46:28Z"),
                pipeline(2, "2026-10-25T03:00:00Z", sha="bbb"),
            ],
            "pipelines/1/jobs": [job("lint", 30.0), job("test", 61.0)],
            "pipelines/2/jobs": [job("lint", 20.0)],
        }
    )
    row = cost_log.row_for(gitlab, mr_iid=9, what="Developer Flow", session="https://x/s/1")
    cells = [c.strip() for c in row.strip("|").split("|")]
    assert cells[0] == "2026-10-24 23:46"
    assert cells[1] == "Developer Flow"
    assert "!9" in cells
    assert cells[4:7] == ["human", "human", "human"]
    assert "[1](https://gitlab.com/g/p/-/pipelines/1)" in row
    assert "[2](https://gitlab.com/g/p/-/pipelines/2)" in row
    assert cells[8:11] == ["4", "111.0", "0"]


def test_unmeasurable_duration_is_null_never_zero() -> None:
    gitlab = fake_gitlab(
        {
            "merge_requests/9/pipelines": [pipeline(1, "2026-10-25T02:46:28Z")],
            "pipelines/1/jobs": [job("lint", 30.0), job("test", None)],
        }
    )
    cells = [c.strip() for c in cost_log.row_for(gitlab, mr_iid=9).strip("|").split("|")]
    assert cells[8:10] == ["null", "null"]


def test_retries_are_counted_from_repeated_jobs() -> None:
    gitlab = fake_gitlab(
        {
            "merge_requests/9/pipelines": [pipeline(1, "2026-10-25T02:46:28Z")],
            "pipelines/1/jobs": [job("test", 10.0), job("test", 12.0)],
        }
    )
    cells = [c.strip() for c in cost_log.row_for(gitlab, mr_iid=9).strip("|").split("|")]
    assert cells[10] == "1"


def test_pipelines_by_id_are_read_one_by_one() -> None:
    gitlab = fake_gitlab(
        {
            "pipelines/5": pipeline(5, "2026-10-25T02:46:28Z", source="duo_workflow"),
            "pipelines/5/jobs": [job("workload", 79.0)],
        }
    )
    row = cost_log.row_for(gitlab, pipeline_ids=[5], what="Fix CI/CD Pipeline")
    assert "[5](https://gitlab.com/g/p/-/pipelines/5)" in row
    assert row.endswith("|")


def test_no_pipeline_is_an_error_not_an_empty_row() -> None:
    gitlab = fake_gitlab({"merge_requests/9/pipelines": []})
    with pytest.raises(cost_log.CostLogError, match="no pipeline"):
        cost_log.row_for(gitlab, mr_iid=9)


def test_a_target_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    assert cost_log.main([]) == 2
    assert "--mr or --pipeline" in capsys.readouterr().err


def test_header_matches_the_row_width() -> None:
    gitlab = fake_gitlab(
        {
            "merge_requests/9/pipelines": [pipeline(1, "2026-10-25T02:46:28Z")],
            "pipelines/1/jobs": [job("lint", 30.0)],
        }
    )
    columns = len(cost_log.COLUMNS)
    assert len(cost_log.row_for(gitlab, mr_iid=9).strip("|").split("|")) == columns
