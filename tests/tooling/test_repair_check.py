"""repair_check: does the repair merge request fix the jobs the autoheal issue listed?"""

import json
from typing import Any

import pytest

from scripts import repair_check
from scripts.afaw_state.facts import FactsError
from scripts.repair_check import check, failed_jobs

API = "https://gitlab.example/api/v4"


def issue_text(*jobs: tuple[str, str]) -> str:
    facts = "\n".join(f"- `{name}` (stage {stage})" for name, stage in jobs)
    logs = "\n".join(f"End of the log of `{name}`:\n```text\nboom\n```" for name, _ in jobs)
    return (
        "A pipeline failed on branch `main` at commit abc12345. Repair it.\n\n"
        f"Failed jobs:\n{facts}\n\n{logs}\n\n<!-- afaw-autoheal ref=main -->"
    )


def job(name: str, status: str, jid: int = 1) -> dict[str, Any]:
    return {"id": jid, "name": name, "status": status}


# ------------------------------------------------------------------ failed_jobs


def test_failed_jobs_with_one_job():
    assert failed_jobs(issue_text(("lint", "verify"))) == ["lint"]


def test_failed_jobs_with_several_jobs_keeps_the_listed_order():
    text = issue_text(("lint", "verify"), ("unit tests", "verify"), ("mutation_gate", "secure"))
    assert failed_jobs(text) == ["lint", "unit tests", "mutation_gate"]


def test_failed_jobs_with_no_failed_jobs_section_is_empty():
    assert failed_jobs("A pipeline failed. Nothing is listed here.") == []


def test_failed_jobs_with_an_empty_section_is_empty():
    assert failed_jobs("Failed jobs:\n\nEnd of the log of `lint`:") == []


def test_failed_jobs_ignores_bullets_outside_the_section():
    text = "- `other` (stage x)\n\n" + issue_text(("lint", "verify")) + "\n- `after` (stage y)"
    assert failed_jobs(text) == ["lint"]


def test_failed_jobs_reads_a_job_without_a_stage_marker():
    assert failed_jobs("Failed jobs:\n- `lint` (stage ?)\n") == ["lint"]


def test_failed_jobs_does_not_repeat_a_name():
    assert failed_jobs("Failed jobs:\n- `lint` (stage a)\n- `lint` (stage a)\n") == ["lint"]


# ------------------------------------------------------------------ check


def test_every_listed_job_green_is_ok():
    result = check(["lint", "unit"], [job("lint", "success", 1), job("unit", "success", 2)])
    assert result == {"ok": True, "fixed": ["lint", "unit"], "still_failing": [], "missing": []}


def test_a_job_that_still_fails_is_not_ok():
    result = check(["lint", "unit"], [job("lint", "success", 1), job("unit", "failed", 2)])
    assert result == {"ok": False, "fixed": ["lint"], "still_failing": ["unit"], "missing": []}


def test_a_job_that_did_not_run_is_missing_and_not_a_pass():
    result = check(["lint", "unit"], [job("lint", "success", 1)])
    assert result == {"ok": False, "fixed": ["lint"], "still_failing": [], "missing": ["unit"]}


@pytest.mark.parametrize("status", ["canceled", "skipped", "running", "manual", "pending"])
def test_a_job_that_ran_without_success_is_still_failing(status):
    assert check(["lint"], [job("lint", status)])["still_failing"] == ["lint"]


def test_a_job_that_ran_twice_the_last_attempt_wins_when_it_passed():
    jobs = [job("lint", "failed", 1), job("lint", "success", 2)]
    assert check(["lint"], jobs)["ok"] is True


def test_a_job_that_ran_twice_the_last_attempt_wins_when_it_failed():
    jobs = [job("lint", "success", 1), job("lint", "failed", 2)]
    assert check(["lint"], jobs) == {
        "ok": False,
        "fixed": [],
        "still_failing": ["lint"],
        "missing": [],
    }


def test_the_last_attempt_is_the_highest_id_whatever_the_list_order():
    jobs = [job("lint", "success", 9), job("lint", "failed", 3)]
    assert check(["lint"], jobs)["ok"] is True


def test_jobs_that_were_not_listed_do_not_matter():
    jobs = [job("lint", "success", 1), job("docs", "failed", 2)]
    assert check(["lint"], jobs)["ok"] is True


def test_nothing_to_verify_is_not_ok():
    assert check([], [job("lint", "success")]) == {
        "ok": False,
        "fixed": [],
        "still_failing": [],
        "missing": [],
    }


# ------------------------------------------------------------------ CLI


def fake_get_json(jobs: list[dict[str, Any]], description: str, pipelines=None):
    seen: list[str] = []
    pipelines = [{"id": 10, "created_at": "2026-10-26T01:00:00Z"}] if pipelines is None else pipelines

    def get_json(url: str) -> Any:
        seen.append(url)
        if "/issues/5" in url:
            return {"description": description}
        if "/merge_requests/9/pipelines" in url:
            return pipelines
        if "/pipelines/" in url and "/jobs" in url:
            return jobs
        raise AssertionError(f"unexpected URL {url}")

    get_json.seen = seen  # type: ignore[attr-defined]
    return get_json


ARGS = ["--api-url", API, "--project", "42", "--issue", "5", "--mr", "9"]


def test_cli_exits_0_and_prints_json_when_the_repair_fixed_the_job(capsys):
    api = fake_get_json([job("lint", "success")], issue_text(("lint", "verify")))
    assert repair_check.main(ARGS, get_json=api) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": True, "fixed": ["lint"], "still_failing": [], "missing": []}


def test_cli_exits_1_when_a_job_still_fails(capsys):
    api = fake_get_json([job("lint", "failed")], issue_text(("lint", "verify")))
    assert repair_check.main(ARGS, get_json=api) == 1
    assert json.loads(capsys.readouterr().out)["still_failing"] == ["lint"]


def test_cli_reads_the_jobs_of_the_latest_pipeline_with_retried_attempts():
    pipelines = [
        {"id": 10, "created_at": "2026-10-26T01:00:00Z"},
        {"id": 11, "created_at": "2026-10-26T02:00:00Z"},
    ]
    api = fake_get_json([job("lint", "success")], issue_text(("lint", "verify")), pipelines)
    repair_check.main(ARGS, get_json=api)
    jobs_urls = [u for u in api.seen if "/jobs" in u]
    assert jobs_urls
    assert all("/projects/42/pipelines/11/jobs" in u for u in jobs_urls)
    assert all("include_retried=true" in u for u in jobs_urls)


def test_cli_with_no_pipeline_for_the_merge_request_exits_1(capsys):
    api = fake_get_json([], issue_text(("lint", "verify")), pipelines=[])
    assert repair_check.main(ARGS, get_json=api) == 1
    assert json.loads(capsys.readouterr().out)["missing"] == ["lint"]


def test_cli_exits_2_when_the_api_cannot_be_read(capsys):
    def broken(url: str) -> Any:
        raise FactsError("GET failed after 4 attempts (HTTP 503)")

    assert repair_check.main(ARGS, get_json=broken) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "repair_check" in captured.err


def test_cli_exits_2_when_the_issue_lists_no_failed_job(capsys):
    api = fake_get_json([job("lint", "success")], "Nothing is listed here.")
    assert repair_check.main(ARGS, get_json=api) == 2
    assert "Failed jobs" in capsys.readouterr().err


def test_cli_exits_2_on_an_answer_it_cannot_read(capsys):
    def odd(url: str) -> Any:
        return {"unexpected": True}

    assert repair_check.main(ARGS, get_json=odd) == 2


def test_cli_api_url_defaults_to_the_ci_environment(monkeypatch):
    monkeypatch.setenv("CI_API_V4_URL", API)
    api = fake_get_json([job("lint", "success")], issue_text(("lint", "verify")))
    assert repair_check.main(["--project", "42", "--issue", "5", "--mr", "9"], get_json=api) == 0
    assert all(u.startswith(f"{API}/projects/42/") for u in api.seen)


def test_cli_api_url_defaults_to_gitlab_com_outside_ci(monkeypatch):
    monkeypatch.delenv("CI_API_V4_URL", raising=False)
    api = fake_get_json([job("lint", "success")], issue_text(("lint", "verify")))
    repair_check.main(["--project", "42", "--issue", "5", "--mr", "9"], get_json=api)
    assert all(u.startswith("https://gitlab.com/api/v4/projects/42/") for u in api.seen)
